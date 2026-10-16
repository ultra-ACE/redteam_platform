import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.db.session import SessionLocal
from app.services import (
    JudgeEvaluationService,
    ReportAutomationService,
    ReportService,
    RuleValidationService,
    TaskExecutionService,
    UnitOfWork,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _run_task_case_async(task_case_id: int, celery_task_id: str | None) -> int | None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        return await service.run_task_case(task_case_id, celery_task_id=celery_task_id)


@celery_app.task(name="workers.dispatch_task")
def dispatch_task(task_id: int) -> None:
    logger.info("dispatch task %s", task_id)
    execute_task.delay(task_id)


@celery_app.task(name="workers.execute_task")
def execute_task(task_id: int) -> list[int]:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        all_case_ids = service.expand_task(task_id)
        uow.commit()

    # 只派发 pending 状态的用例；已成功/已失败/已取消不重跑
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        pending_ids = TaskExecutionService(uow).list_pending_case_ids(task_id)

    for task_case_id in pending_ids:
        run_task_case.delay(task_case_id)
    return all_case_ids


@celery_app.task(name="workers.dispatch_pending_task")
def dispatch_pending_task(task_id: int) -> list[int]:
    """resume 专用：只派发 pending 用例。"""
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        pending_ids = TaskExecutionService(uow).list_pending_case_ids(task_id)
        task = uow.evaluation_tasks.get(task_id)
        if task is not None and task.status in {"paused", "draft"}:
            task.status = "queued"
        uow.commit()

    for task_case_id in pending_ids:
        run_task_case.delay(task_case_id)
    logger.info("dispatch pending task %s -> %d cases", task_id, len(pending_ids))
    return pending_ids


@celery_app.task(name="workers.dispatch_recovery")
def dispatch_recovery() -> dict[str, int]:
    """手动触发恢复：用于 Worker 启动信号之外的人工排查。"""
    from app.workers.recovery import recover_incomplete_tasks

    summary = recover_incomplete_tasks()
    for task_case_id in summary.pop("pending_case_ids", []):
        run_task_case.delay(task_case_id)
    return summary


@celery_app.task(name="workers.dispatch_failed_task")
def dispatch_failed_task(task_id: int) -> None:
    logger.info("dispatch failed task cases %s", task_id)
    execute_failed_task.delay(task_id)


@celery_app.task(name="workers.execute_failed_task")
def execute_failed_task(task_id: int) -> list[int]:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        task_case_ids = TaskExecutionService(uow).prepare_retry_failed(task_id)
        uow.commit()

    for task_case_id in task_case_ids:
        run_task_case.delay(task_case_id)
    return task_case_ids


@celery_app.task(name="workers.run_task_case", bind=True)
def run_task_case(self, task_case_id: int) -> int | None:
    celery_task_id = getattr(self.request, "id", None)
    attempt_id = _run_async(_run_task_case_async(task_case_id, celery_task_id))
    if attempt_id is not None:
        judge_attempt.delay(attempt_id)
    return attempt_id


@celery_app.task(name="workers.judge_attempt")
def judge_attempt(attempt_id: int) -> None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = JudgeEvaluationService(uow)
        service.evaluate_attempt(attempt_id)
        uow.commit()
    validate_rules.delay(attempt_id)


@celery_app.task(name="workers.validate_rules")
def validate_rules(attempt_id: int) -> None:
    report_id: int | None = None
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        RuleValidationService(uow).validate_attempt(attempt_id)
        attempt = uow.task_attempts.get(attempt_id)
        task_case = uow.task_cases.get(attempt.task_case_id) if attempt else None
        if task_case is not None:
            # 规则处理结束后清空 celery_task_id，表示这次调度完成
            task_case.celery_task_id = None
            report, created = ReportAutomationService(uow).ensure_auto_report(task_case.task_id)
            if created and report is not None:
                report_id = report.id
        uow.commit()
    if report_id is not None:
        generate_report.delay(report_id)


@celery_app.task(name="workers.generate_report")
def generate_report(report_id: int) -> None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        ReportService(uow).generate_report(report_id)
        uow.commit()