import asyncio
import logging
import time

from app.db.session import SessionLocal
from app.services import (
    JudgeEvaluationService,
    ManualReviewService,
    ReportAutomationService,
    ReportService,
    RuleValidationService,
    TaskExecutionService,
    UnitOfWork,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _run_task_case(
    task_case_id: int,
    celery_task_id: str | None,
) -> tuple[int | None, bool]:
    """PAIR 用例必须同步执行（每轮 Judge 内部会 asyncio.run），普通用例走异步链路。"""
    try:
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            service = TaskExecutionService(uow)
            if service.requires_iterative(task_case_id):
                attempt_id = service.run_iterative_task_case(
                    task_case_id,
                    celery_task_id=celery_task_id,
                )
                # PAIR 内部已经完成 Judge、规则校验和人工复核。
                return attempt_id, False
            attempt_id = asyncio.run(
                service.run_task_case(task_case_id, celery_task_id=celery_task_id)
            )
            return attempt_id, True
    except Exception as exc:
        logger.exception("task case %s failed unexpectedly", task_case_id)
        with SessionLocal() as session:
            service = TaskExecutionService(UnitOfWork(session))
            service.fail_task_case(task_case_id, "WORKER_EXCEPTION", str(exc))
        return None, False


@celery_app.task(name="workers.dispatch_task")
def dispatch_task(task_id: int) -> None:
    logger.info("dispatch task %s", task_id)
    execute_task.delay(task_id)


@celery_app.task(name="workers.execute_task")
def execute_task(task_id: int) -> list[int]:
    started = time.perf_counter()
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        all_case_ids = service.expand_task(task_id)
        uow.commit()
    logger.info(
        "task=%s stage=expand elapsed_ms=%d cases=%d",
        task_id,
        _elapsed_ms(started),
        len(all_case_ids),
    )

    # 只派发 pending 状态的用例；已成功/已失败/已取消不重跑
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        pending_ids = service.list_pending_case_ids(task_id)
        if not pending_ids:
            # 重新开始时如果已经没有 pending（用例全部有结论），同样要收尾，
            # 否则任务会停在 queued 不会再有任何进度刷新。
            service.refresh_task_state(task_id)
        uow.commit()

    for task_case_id in pending_ids:
        run_task_case.delay(task_case_id)
    return all_case_ids


@celery_app.task(name="workers.dispatch_pending_task")
def dispatch_pending_task(task_id: int) -> list[int]:
    """resume 专用：只派发 pending 用例。"""
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        task = uow.evaluation_tasks.get(task_id)
        if task is not None and task.status in {"paused", "draft"}:
            task.status = "queued"
        # A task may be persisted as queued/running before expansion finishes.
        # Re-expand it here so resume/recovery cannot strand it at 0/0 forever.
        service.ensure_expanded(task_id)
        pending_ids = service.list_pending_case_ids(task_id)
        if not pending_ids:
            # 没有待跑用例（暂停期间剩的用例已经跑完，或本来就不剩），
            # 不会再有任何 run_task_case 触发进度刷新，必须在这里收尾一次，
            # 否则任务会永远停在 queued，完成数也停在旧值。
            service.refresh_task_state(task_id)
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
    started = time.perf_counter()
    celery_task_id = getattr(self.request, "id", None)
    attempt_id, enqueue_followup = _run_task_case(task_case_id, celery_task_id)
    logger.info(
        "task_case=%s stage=worker_total elapsed_ms=%d attempt_id=%s",
        task_case_id,
        _elapsed_ms(started),
        attempt_id,
    )
    if attempt_id is not None and enqueue_followup:
        judge_attempt.delay(attempt_id)
    return attempt_id


@celery_app.task(name="workers.judge_attempt")
def judge_attempt(attempt_id: int) -> None:
    started = time.perf_counter()
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = JudgeEvaluationService(uow)
        service.evaluate_attempt(attempt_id)
        uow.commit()
    logger.info(
        "attempt=%s stage=judge elapsed_ms=%d",
        attempt_id,
        _elapsed_ms(started),
    )
    validate_rules.delay(attempt_id)


@celery_app.task(name="workers.validate_rules")
def validate_rules(attempt_id: int) -> None:
    report_id: int | None = None
    started = time.perf_counter()
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        RuleValidationService(uow).validate_attempt(attempt_id)
        JudgeEvaluationService(uow).recalculate_trust_scores(attempt_id)
        ManualReviewService(uow).ensure_for_attempt(attempt_id)
        rule_elapsed = _elapsed_ms(started)
        attempt = uow.task_attempts.get(attempt_id)
        task_case = uow.task_cases.get(attempt.task_case_id) if attempt else None
        if task_case is not None:
            # 规则处理结束后清空 celery_task_id，表示这次调度完成
            task_case.celery_task_id = None
            db_started = time.perf_counter()
            report, created = ReportAutomationService(uow).ensure_auto_report(task_case.task_id)
            uow.commit()
            db_elapsed = _elapsed_ms(db_started)
            if created and report is not None:
                report_id = report.id
        else:
            uow.commit()
            db_elapsed = 0
    logger.info(
        "attempt=%s stage=rule elapsed_ms=%d stage=db_finalize elapsed_ms=%d",
        attempt_id,
        rule_elapsed,
        db_elapsed,
    )
    if report_id is not None:
        generate_report.delay(report_id)


@celery_app.task(name="workers.generate_report")
def generate_report(report_id: int) -> None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        ReportService(uow).generate_report(report_id)
        uow.commit()
