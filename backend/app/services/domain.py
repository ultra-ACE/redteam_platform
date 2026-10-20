from pathlib import Path
from typing import Any

from app.adapters import GenerateRequest, GenerateResponse, HealthStatus, build_adapter
from app.db.models import (
    EvaluationTask,
    JudgeProfile,
    ManualReview,
    ModelRegistry,
    TaskModelBinding,
)
from app.services.base import BaseService

#: 已经有结论、不能再被 暂停/恢复 改写的任务状态
TERMINAL_TASK_STATUSES = {"succeeded", "partially_failed", "failed", "cancelled"}


class BenchmarkService(BaseService):
    def list_benchmarks(self, page: int, page_size: int, keyword: str | None = None, status: str | None = None):
        return self.uow.benchmarks.list(page=page, page_size=page_size, status=status)

    def list_versions(self, benchmark_id: int, page: int, page_size: int):
        return self.uow.benchmark_versions.list(
            page=page,
            page_size=page_size,
            benchmark_id=benchmark_id,
        )

    def list_test_cases(
        self,
        page: int,
        page_size: int,
        benchmark_version_id: int | None = None,
        status: str | None = None,
    ):
        return self.uow.test_cases.list(
            page=page,
            page_size=page_size,
            benchmark_version_id=benchmark_version_id,
            status=status,
        )

    def update_test_case(self, test_case_id: int, payload: Any):
        test_case = self.uow.test_cases.get(test_case_id)
        if test_case is None:
            return None
        for field in ("prompt", "system_prompt", "language", "dataset_type", "sample_kind", "status"):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(test_case, field, value)
        self.uow.session.flush()
        return test_case

    def delete_version(self, version_id: int) -> dict[str, int] | None:
        version = self.uow.benchmark_versions.get(version_id)
        if version is None:
            return None
        self._assert_version_unused(version.id)
        summary = self._delete_version(version)
        self.uow.session.flush()
        return summary

    def delete_benchmark(self, benchmark_id: int) -> dict[str, int] | None:
        benchmark = self.uow.benchmarks.get(benchmark_id)
        if benchmark is None:
            return None

        versions = self.uow.benchmark_versions.list(
            page=1,
            page_size=100000,
            benchmark_id=benchmark_id,
        )
        for version in versions:
            self._assert_version_unused(version.id)

        summary = {"deleted_versions": 0, "deleted_test_cases": 0}
        for version in versions:
            partial = self._delete_version(version)
            for key, value in partial.items():
                summary[key] += value

        self.uow.benchmarks.delete(benchmark)
        self.uow.session.flush()
        return summary

    def _assert_version_unused(self, version_id: int) -> None:
        used = self.uow.evaluation_tasks.count(benchmark_version_id=version_id)
        if used:
            raise ValueError(
                f"该 Benchmark 版本已被 {used} 个评测任务引用，无法删除。"
                "请先删除或重建这些评测任务。"
            )

    def _delete_version(self, version) -> dict[str, int]:
        test_cases = self.uow.test_cases.list(
            page=1,
            page_size=100000,
            benchmark_version_id=version.id,
        )
        for test_case in test_cases:
            self.uow.test_cases.delete(test_case)

        source_file_id = version.source_file_id
        self.uow.benchmark_versions.delete(version)
        self.uow.session.flush()

        if source_file_id:
            still_used = self.uow.benchmark_versions.count(source_file_id=source_file_id)
            if not still_used:
                stored_file = self.uow.files.get(source_file_id)
                if stored_file is not None:
                    try:
                        file_path = Path(stored_file.stored_path)
                        if file_path.exists():
                            file_path.unlink()
                    except OSError:
                        pass
                    self.uow.files.delete(stored_file)
                    self.uow.session.flush()

        return {"deleted_versions": 1, "deleted_test_cases": len(test_cases)}


class ModelService(BaseService):
    def list_models(self, page: int, page_size: int, usage_scope: str | None = None, enabled: bool | None = None):
        return self.uow.models.list(
            page=page,
            page_size=page_size,
            usage_scope=usage_scope,
            enabled=enabled,
        )

    def create_model(self, payload: Any) -> ModelRegistry:
        model = ModelRegistry(
            name=payload.name,
            provider=payload.provider,
            adapter_type=payload.adapter_type.value if hasattr(payload.adapter_type, "value") else payload.adapter_type,
            base_url=payload.base_url,
            model_name=payload.model_name,
            secret_ref=payload.secret_ref,
            default_params=payload.default_params,
            usage_scope=payload.usage_scope.value if hasattr(payload.usage_scope, "value") else payload.usage_scope,
            enabled=payload.enabled,
        )
        return self.uow.models.add(model)

    def update_model(self, model_id: int, payload: Any) -> ModelRegistry | None:
        model = self.uow.models.get(model_id)
        if model is None:
            return None
        for field in (
            "name",
            "provider",
            "adapter_type",
            "base_url",
            "model_name",
            "secret_ref",
            "default_params",
            "usage_scope",
            "enabled",
        ):
            value = getattr(payload, field, None)
            if value is not None:
                if hasattr(value, "value"):
                    value = value.value
                if field == "secret_ref":
                    # 前端只拿到掩码；回传掩码或留空都表示"不修改"
                    text = str(value).strip()
                    if not text or "****" in text:
                        continue
                    value = text
                setattr(model, field, value)
        self.uow.session.flush()
        return model

    async def health_check(self, model_id: int) -> HealthStatus | None:
        model = self.uow.models.get(model_id)
        if model is None:
            return None
        return await build_adapter(model).health_check()

    async def generate(self, model_id: int, request: GenerateRequest) -> GenerateResponse | None:
        model = self.uow.models.get(model_id)
        if model is None:
            return None
        return await build_adapter(model).generate(request)


class TaskService(BaseService):
    def create_task(self, payload: Any, created_by: str = "local") -> EvaluationTask:
        seed_ids = list(dict.fromkeys(payload.seed_test_case_ids or []))
        self._validate_seed_ids(seed_ids)
        task = EvaluationTask(
            name=payload.name,
            benchmark_version_id=payload.benchmark_version_id,
            status="queued",
            priority=payload.priority,
            created_by=created_by,
            config=payload.model_dump(mode="json"),
            total_cases=0,
        )
        self.uow.evaluation_tasks.add(task)
        for binding in payload.model_bindings:
            self.uow.task_model_bindings.add(
                TaskModelBinding(
                    task_id=task.id,
                    model_id=binding.model_id,
                    role=binding.role,
                    model_params=binding.model_params,
                    enabled=binding.enabled,
                )
            )
        return task

    def _validate_seed_ids(self, seed_ids: list[int]) -> None:
        """种子必须存在且处于启用状态，避免任务创建后才发现无效。"""
        missing = [
            seed_id
            for seed_id in seed_ids
            if (test_case := self.uow.test_cases.get(seed_id)) is None
            or test_case.status != "active"
        ]
        if missing:
            preview = ", ".join(str(item) for item in missing[:10])
            raise ValueError(f"种子不存在或已停用: {preview}")

    def list_tasks(self, page: int, page_size: int, status: str | None = None):
        return self.uow.evaluation_tasks.list(page=page, page_size=page_size, status=status)

    def get_task(self, task_id: int) -> EvaluationTask | None:
        return self.uow.evaluation_tasks.get(task_id)

    def get_status_snapshot(self, task_id: int) -> dict[str, Any] | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None
        running_cases = self.uow.task_cases.count(task_id=task_id, status="running")
        return {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "total_cases": task.total_cases,
            "completed_cases": task.completed_cases,
            "failed_cases": task.failed_cases,
            "running_cases": running_cases,
            "current_stage": self._current_stage(task),
            "queue_position": None,
            "eta_seconds": None,
            "cancel_requested": task.cancel_requested,
            "pause_requested": task.pause_requested,
            "last_heartbeat_at": task.last_heartbeat_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        }

    @staticmethod
    def _current_stage(task: EvaluationTask) -> str:
        if task.status in {"queued", "paused"}:
            return task.status
        if task.status == "running":
            if task.total_cases and task.completed_cases + task.failed_cases >= task.total_cases:
                return "finalizing"
            return "executing"
        return task.status

    def pause_task(self, task_id: int) -> EvaluationTask | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None
        # 已经有结论的任务不允许再被改成 paused，否则会覆盖掉完成状态
        if task.status in TERMINAL_TASK_STATUSES:
            return task
        task.pause_requested = True
        task.status = "paused"
        self.uow.session.flush()
        return task

    def resume_task(self, task_id: int) -> EvaluationTask | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None
        task.pause_requested = False
        task.cancel_requested = False
        task.status = "queued"
        task.finished_at = None
        self.uow.session.flush()
        return task

    def cancel_task(self, task_id: int) -> EvaluationTask | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None
        task.status = "cancelled"
        task.cancel_requested = True
        self.uow.session.flush()
        return task


class JudgeService(BaseService):
    def list_profiles(self, page: int, page_size: int):
        return self.uow.judge_profiles.list(page=page, page_size=page_size)

    def create_profile(self, payload: Any) -> JudgeProfile:
        profile = JudgeProfile(
            name=payload.name,
            judge_type=payload.judge_type.value if hasattr(payload.judge_type, "value") else payload.judge_type,
            judge_model_id=payload.judge_model_id,
            strategy=payload.strategy,
            prompt_template=payload.prompt_template,
            params=payload.params,
        )
        return self.uow.judge_profiles.add(profile)


class ReviewService(BaseService):
    def list_reviews(self, page: int, page_size: int, status: str | None = None):
        return self.uow.manual_reviews.list(page=page, page_size=page_size, status=status)

    def create_review(self, payload: Any, reviewer: str = "local") -> ManualReview:
        review = ManualReview(
            task_attempt_id=payload.task_attempt_id,
            trigger_reason=payload.trigger_reason,
            status="resolved",
            reviewer=reviewer,
            decision=payload.decision.value if hasattr(payload.decision, "value") else payload.decision,
            corrected_verdict=payload.corrected_verdict,
            comment=payload.comment,
        )
        return self.uow.manual_reviews.add(review)
