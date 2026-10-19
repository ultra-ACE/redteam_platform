from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.adapters import AdapterError, GenerateRequest, build_adapter
from app.db.models import (
    EvaluationTask,
    TaskAttempt,
    TaskCase,
    TestCase,
)
from app.services.base import BaseService


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TaskExecutionService(BaseService):
    def expand_task(self, task_id: int) -> list[int]:
        """把任务展开为 task_cases；返回所有用例 ID（含已存在的），但保留其原状态。

        真正的入队由 ``dispatch_pending_task_cases`` 只挑 pending 的记录，所以
        已成功/已失败的用例不会被重复执行。
        """
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return []

        bindings = self._target_bindings(task.id)
        if not bindings:
            task.status = "failed"
            task.error_message = "no enabled target model binding"
            task.total_cases = 0
            task.progress = 0.0
            task.finished_at = _now()
            self.uow.session.flush()
            return []

        test_cases = self.uow.test_cases.list(
            page=1,
            page_size=100000,
            benchmark_version_id=task.benchmark_version_id,
            status="active",
        )
        if not test_cases:
            task.status = "failed"
            task.error_message = "no active test cases"
            task.total_cases = 0
            task.progress = 0.0
            task.finished_at = _now()
            self.uow.session.flush()
            return []

        config = task.config or {}
        attack_template_ids: list[int | None] = config.get("attack_template_ids") or [None]
        if not attack_template_ids:
            attack_template_ids = [None]

        task_case_ids: list[int] = []
        for test_case in test_cases:
            for attack_template_id in attack_template_ids:
                legacy_key = f"{test_case.id}:{attack_template_id or 0}"
                for binding in bindings:
                    case_key = f"{legacy_key}:{binding.model_id}"
                    existing = self.uow.task_cases.list(
                        page=1,
                        page_size=1,
                        task_id=task.id,
                        case_key=case_key,
                    )
                    if existing:
                        self._set_case_model(existing[0], binding.model_id)
                        task_case_ids.append(existing[0].id)
                        continue

                    legacy_cases = self.uow.task_cases.list(
                        page=1,
                        page_size=1,
                        task_id=task.id,
                        case_key=legacy_key,
                    )
                    if legacy_cases and not (legacy_cases[0].case_config or {}).get("model_id"):
                        self._set_case_model(legacy_cases[0], binding.model_id)
                        task_case_ids.append(legacy_cases[0].id)
                        continue

                    task_case = TaskCase(
                        task_id=task.id,
                        test_case_id=test_case.id,
                        attack_template_id=attack_template_id,
                        case_key=case_key,
                        status="pending",
                        case_config={"model_id": binding.model_id},
                    )
                    self.uow.task_cases.add(task_case)
                    task_case_ids.append(task_case.id)

        task.total_cases = len(task_case_ids)
        if task.status in {"draft", "queued"}:
            task.progress = 0.0
        self.uow.session.flush()
        return task_case_ids

    def list_pending_case_ids(self, task_id: int) -> list[int]:
        """只返回 pending 状态的用例 ID，用于 resume / recovery 重新入队。"""
        rows = self.uow.task_cases.list(
            page=1,
            page_size=100000,
            task_id=task_id,
        )
        return [row.id for row in rows if row.status == "pending"]

    async def run_task_case(
        self,
        task_case_id: int,
        celery_task_id: str | None = None,
    ) -> int | None:
        task_case = self.uow.task_cases.get(task_case_id)
        if task_case is None:
            return None
        task = self.uow.evaluation_tasks.get(task_case.task_id)
        if task is None:
            return None

        # 1) 取消优先级最高
        if task.cancel_requested:
            task_case.status = "cancelled"
            self.uow.session.flush()
            # 必须提交：Session 关闭时会回滚未提交的改动，用例会一直停在 pending
            self.uow.commit()
            return None

        # 2) 暂停：不派发新用例，保持 pending，等待 resume
        if task.pause_requested:
            if task_case.status not in {"succeeded", "failed", "cancelled"}:
                task_case.status = "pending"
            self.uow.session.flush()
            self.uow.commit()
            return None

        # 3) 已终止的用例绝不重跑
        if task_case.status in {"succeeded", "cancelled"}:
            return None

        # 4) 保存 Celery task id 用于恢复时判断是否还有在跑的任务
        if celery_task_id:
            task_case.celery_task_id = celery_task_id

        test_case = self.uow.test_cases.get(task_case.test_case_id)
        if test_case is None:
            task_case.status = "failed"
            task_case.last_heartbeat_at = _now()
            # 同样要刷新并提交，否则这条失败既不会计入进度、也会被 Session 关闭回滚
            self._refresh_task_progress(task)
            self.uow.session.flush()
            self.uow.commit()
            return None

        model_id = (task_case.case_config or {}).get("model_id")
        binding = self._find_target_binding(task.id, model_id)
        if binding is None:
            return self._fail_before_attempt(task, task_case, "MODEL_BINDING_MISSING", "target model binding not found")
        model = self.uow.models.get(binding.model_id)
        if model is None:
            return self._fail_before_attempt(task, task_case, "MODEL_NOT_FOUND", "target model not found")

        prompt = self._render_prompt(test_case, task_case)
        model_params = binding.model_params or {}
        started_at = _now()
        attempt = TaskAttempt(
            task_case_id=task_case.id,
            model_id=model.id,
            attempt_no=task_case.retry_count + 1,
            input_snapshot={
                "prompt": prompt,
                "system_prompt": test_case.system_prompt,
                "model_params": model_params,
            },
            status="running",
            started_at=started_at,
            last_heartbeat_at=started_at,
        )
        self.uow.task_attempts.add(attempt)
        task_case.status = "running"
        task_case.last_heartbeat_at = started_at
        task.status = "running"
        if task.started_at is None:
            task.started_at = started_at
        self.uow.session.flush()
        self.uow.commit()

        adapter = build_adapter(model)
        request = GenerateRequest(
            prompt=prompt,
            system_prompt=test_case.system_prompt,
            temperature=float(model_params.get("temperature", 0.2)),
            max_tokens=int(model_params.get("max_tokens", 1024)),
            extra={key: value for key, value in model_params.items() if key not in {"temperature", "max_tokens"}},
        )

        try:
            response = await adapter.generate(request)
        except AdapterError as exc:
            finished_at = _now()
            attempt.status = "failed"
            attempt.error_code = "MODEL_REQUEST_FAILED"
            attempt.error_message = str(exc)
            attempt.finished_at = finished_at
            attempt.last_heartbeat_at = finished_at
            task_case.status = "failed"
            task_case.last_heartbeat_at = finished_at
            
            self._refresh_task_progress(task)
            
            self.uow.session.flush()
            self.uow.commit()
            return attempt.id

        finished_at = _now()
        attempt.status = "succeeded"
        attempt.output_text = response.text
        attempt.latency_ms = response.latency_ms
        attempt.prompt_tokens = response.prompt_tokens
        attempt.completion_tokens = response.completion_tokens
        attempt.finished_at = finished_at
        attempt.last_heartbeat_at = finished_at
        task_case.status = "succeeded"
        task_case.last_heartbeat_at = finished_at
        
        self._refresh_task_progress(task)
        
        self.uow.session.flush()
        self.uow.commit()
        return attempt.id

    def touch_heartbeat(self, task_case_id: int) -> None:
        """让正在执行的用例更新心跳，Worker 被 kill 后由 recovery 依据超时回滚。"""
        now = _now()
        task_case = self.uow.task_cases.get(task_case_id)
        if task_case is None:
            return
        task_case.last_heartbeat_at = now
        running_attempts = self.uow.task_attempts.list(
            page=1,
            page_size=10,
            task_case_id=task_case_id,
            status="running",
        )
        for attempt in running_attempts:
            attempt.last_heartbeat_at = now
        self.uow.session.flush()

    def prepare_retry_failed(self, task_id: int) -> list[int]:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return []

        task_cases = self.uow.task_cases.list(
            page=1,
            page_size=100000,
            task_id=task_id,
            order_by=TaskCase.id,
        )
        failed_cases = [task_case for task_case in task_cases if task_case.status in {"failed", "timeout"}]
        if not failed_cases:
            self._refresh_task_progress(task)
            self.uow.session.flush()
            return []

        for task_case in failed_cases:
            task_case.status = "pending"
            task_case.retry_count += 1
        self.uow.session.flush()

        self._refresh_task_progress(task)
        
        # 强制把主状态切回 queued，以便重新派发
        task.status = "queued"
        task.cancel_requested = False
        task.pause_requested = False
        task.error_message = None
        task.finished_at = None
        self.uow.session.flush()
        return [task_case.id for task_case in failed_cases]

    def _target_bindings(self, task_id: int):
        bindings = self.uow.task_model_bindings.list(
            page=1,
            page_size=100,
            task_id=task_id,
            enabled=True,
        )
        target_bindings = [binding for binding in bindings if binding.role == "target"]
        return target_bindings or bindings

    def _find_target_binding(self, task_id: int, model_id: int | None = None):
        bindings = self._target_bindings(task_id)
        if model_id is not None:
            return next((binding for binding in bindings if binding.model_id == model_id), None)
        return bindings[0] if bindings else None

    @staticmethod
    def _set_case_model(task_case: TaskCase, model_id: int) -> None:
        case_config = dict(task_case.case_config or {})
        case_config["model_id"] = model_id
        task_case.case_config = case_config

    def _render_prompt(self, test_case: TestCase, task_case: TaskCase) -> str:
        prompt = test_case.prompt
        if task_case.attack_template_id is None:
            return prompt
        template = self.uow.attack_templates.get(task_case.attack_template_id)
        if template is None:
            return prompt
        template_text = template.template_text
        # 官方模板可能用 {0}/{seed}/{behavior}，也可能没有占位符
        has_placeholder = any(
            token in template_text for token in ("{prompt}", "{0}", "{seed}", "{behavior}")
        )
        for alias in ("{0}", "{seed}", "{behavior}"):
            template_text = template_text.replace(alias, prompt)
        # 模板漏写占位符时把原始问题补在末尾，避免只把模板本身发给模型
        template_text = template_text.replace("{prompt}", prompt)
        if not has_placeholder:
            template_text = f"{template_text.rstrip()}\n\n{prompt}"
        return template_text.replace("{system_prompt}", test_case.system_prompt or "")

    def _fail_before_attempt(self, task: EvaluationTask, task_case: TaskCase, code: str, message: str) -> int:
        now = _now()
        attempt = TaskAttempt(
            task_case_id=task_case.id,
            model_id=0,
            attempt_no=task_case.retry_count + 1,
            status="failed",
            error_code=code,
            error_message=message,
            started_at=now,
            finished_at=now,
            last_heartbeat_at=now,
        )
        self.uow.task_attempts.add(attempt)
        task_case.status = "failed"
        task_case.last_heartbeat_at = now
        
        self._refresh_task_progress(task)
        
        self.uow.session.flush()
        self.uow.commit()
        return attempt.id

    def refresh_task_state(self, task_id: int) -> None:
        """没有用例可派发时也要收尾（resume / recovery 场景）。

        例如暂停期间剩下的用例已经在后台跑完，恢复后 ``pending`` 为空：
        此时没有任何 ``run_task_case`` 会再触发一次进度刷新，任务就会永远停在
        ``queued``。所以派发之前/之后必须无条件刷新一次。
        """
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return
        self._refresh_task_progress(task)
        self.uow.session.flush()

    def _refresh_task_progress(self, task: EvaluationTask) -> None:
        """把用例的真实完成情况汇总回主任务表，并决定任务是否已经结束。

        这里踩过两个坑，改之前请务必保留下面两步：

        1. ``SessionLocal`` 是 ``autoflush=False``，所以必须先 ``flush``。
           否则下面的 COUNT 看不到本事务里刚写入的那条用例状态，
           completed/failed 永远差一条，进度到不了 100%，任务就永远不会收尾
           （表现：用例全跑完了，任务还停在 queued/running，完成数少 1）。
        2. 多个 Worker 会同时刷新同一个任务，先对任务行加锁再统计，
           保证拿到的是"别的用例已经提交之后"的计数，
           也不会把已经结束的任务再改回 running。
        """
        # 1. 先落地本事务内的用例状态变化（autoflush=False 时 COUNT 看不到未 flush 的改动）
        self.uow.session.flush()

        # 2. 锁住任务行，读最新的暂停/取消标志（内存里的 task 可能在模型调用期间过期）
        row = self.uow.session.execute(
            select(
                EvaluationTask.status,
                EvaluationTask.finished_at,
                EvaluationTask.pause_requested,
                EvaluationTask.cancel_requested,
            )
            .where(EvaluationTask.id == task.id)
            .with_for_update()
        ).one_or_none()
        if row is None:
            return
        current_status, current_finished_at, pause_requested, cancel_requested = row

        # 3. 统计真实进度
        total = self.uow.task_cases.count(task_id=task.id)
        completed = self.uow.task_cases.count(task_id=task.id, status="succeeded")
        failed = self.uow.task_cases.count(task_id=task.id, status="failed")
        finished = completed + failed
        progress = 0.0 if total == 0 else min(1.0, finished / total)

        # 4. 同步内存对象，防止调用方读到旧数据
        task.total_cases = total
        task.completed_cases = completed
        task.failed_cases = failed
        task.progress = progress
        task.pause_requested = pause_requested
        task.cancel_requested = cancel_requested
        task.finished_at = current_finished_at

        # 暂停/取消期间只更新计数，不改主状态（取消由 cancel_task 负责收尾）
        if pause_requested or cancel_requested:
            return

        if total > 0 and finished >= total:
            # 5. 全部用例都有结论 -> 收尾
            if failed == 0:
                final_status = "succeeded"
            elif completed == 0:
                final_status = "failed"
            else:
                final_status = "partially_failed"
            task.status = final_status
            if task.finished_at is None:
                task.finished_at = _now()
        elif current_status in {"queued", "draft"}:
            # 有进度了但还没结束：queued/draft -> running
            task.status = "running"
        else:
            # 其它情况（running / 已结束）保持数据库里的状态，只是同步一下内存对象
            task.status = current_status
