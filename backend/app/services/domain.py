from typing import Any

from app.adapters import GenerateRequest, GenerateResponse, HealthStatus, build_adapter
from app.db.models import (
    AttackMethod,
    AuditLog,
    AttackTemplate,
    EvaluationTask,
    JudgeProfile,
    ManualReview,
    ModelRegistry,
    Report,
    RiskTaxonomy,
    SystemConfig,
    TaskModelBinding,
)
from app.services.base import BaseService


class SystemService(BaseService):
    def list_configs(self, page: int, page_size: int) -> list[SystemConfig]:
        return self.uow.system_configs.list(page=page, page_size=page_size)

    def update_config(self, config_key: str, config_value: Any) -> SystemConfig:
        config = self.uow.system_configs.get_by_key(config_key)
        if config is None:
            config = SystemConfig(config_key=config_key, config_value=config_value)
            return self.uow.system_configs.add(config)
        config.config_value = config_value
        self.uow.session.flush()
        return config

    def list_audit_logs(self, page: int, page_size: int):
        return self.uow.audit_logs.list(
            page=page,
            page_size=page_size,
            order_by=AuditLog.id.desc(),
        )


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
        for field in ("prompt", "system_prompt", "language", "status"):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(test_case, field, value)
        self.uow.session.flush()
        return test_case


class RiskService(BaseService):
    def list_taxonomies(self, page: int, page_size: int):
        return self.uow.risk_taxonomies.list(page=page, page_size=page_size)

    def create_taxonomy(self, name: str, version: str, description: str | None, is_default: bool) -> RiskTaxonomy:
        taxonomy = RiskTaxonomy(
            name=name,
            version=version,
            description=description,
            is_default=is_default,
        )
        return self.uow.risk_taxonomies.add(taxonomy)

    def list_categories(self, taxonomy_id: int):
        return self.uow.risk_categories.list(
            page=1,
            page_size=1000,
            taxonomy_id=taxonomy_id,
        )

    def batch_upsert_mappings(self, benchmark_version_id: int, mappings: list[Any]) -> dict[str, int]:
        created = 0
        for item in mappings:
            entity = self.uow.benchmark_risk_mappings.model(
                benchmark_version_id=benchmark_version_id,
                raw_label=item.raw_label,
                risk_category_id=item.risk_category_id,
                mapping_type=item.mapping_type,
                confidence=item.confidence,
                mapping_note=item.mapping_note,
            )
            self.uow.benchmark_risk_mappings.add(entity)
            created += 1
        return {"created_count": created, "updated_count": 0, "remaining_unresolved_count": 0}

    def get_assessment(self, attempt_id: int, score_version: str = "risk-v1"):
        return self.uow.risk_assessments.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            score_version=score_version,
        )


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

    async def health_check(self, model_id: int) -> HealthStatus | None:
        model = self.uow.models.get(model_id)
        if model is None:
            return None
        adapter = build_adapter(model)
        return await adapter.health_check()

    async def generate(self, model_id: int, request: GenerateRequest) -> GenerateResponse | None:
        model = self.uow.models.get(model_id)
        if model is None:
            return None
        adapter = build_adapter(model)
        return await adapter.generate(request)


class AttackService(BaseService):
    def list_methods(self, page: int, page_size: int, enabled: bool | None = None):
        return self.uow.attack_methods.list(page=page, page_size=page_size, enabled=enabled)

    def create_template(self, payload: Any) -> AttackTemplate:
        template = AttackTemplate(
            attack_method_id=payload.attack_method_id,
            name=payload.name,
            template_text=payload.template_text,
            variables=payload.variables,
            version=payload.version,
        )
        return self.uow.attack_templates.add(template)

    def preview_template(self, template_id: int, variables: dict[str, Any]) -> dict[str, str]:
        template = self.uow.attack_templates.get(template_id)
        if template is None:
            return {"rendered_prompt": ""}
        rendered = template.template_text
        for key, value in variables.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        return {"rendered_prompt": rendered}


class TaskService(BaseService):
    def create_task(self, payload: Any, created_by: str = "local") -> EvaluationTask:
        task = EvaluationTask(
            name=payload.name,
            benchmark_version_id=payload.benchmark_version_id,
            risk_taxonomy_id=payload.risk_taxonomy_id,
            status="queued",
            priority=payload.priority,
            created_by=created_by,
            config=payload.model_dump(),
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

    def list_tasks(self, page: int, page_size: int, status: str | None = None):
        return self.uow.evaluation_tasks.list(page=page, page_size=page_size, status=status)

    def get_task(self, task_id: int) -> EvaluationTask | None:
        task = self.uow.evaluation_tasks.get(task_id)
        return task

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
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        }

    @staticmethod
    def _current_stage(task: EvaluationTask) -> str:
        if task.status == "queued":
            return "queued"
        if task.status == "running":
            if task.total_cases and task.completed_cases + task.failed_cases >= task.total_cases:
                return "finalizing"
            return "executing"
        return task.status

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
            corrected_category_id=payload.corrected_category_id,
            corrected_score=payload.corrected_score,
            comment=payload.comment,
        )
        return self.uow.manual_reviews.add(review)

