import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.db.session import SessionLocal
from app.services import (
    AuditLogService,
    JudgeEvaluationService,
    ReportAutomationService,
    ReportService,
    RiskScoringService,
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


async def _run_task_case_async(task_case_id: int) -> int | None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        return await service.run_task_case(task_case_id)


@celery_app.task(name="workers.dispatch_task")
def dispatch_task(task_id: int) -> None:
    logger.info("dispatch task %s", task_id)
    execute_task.delay(task_id)


@celery_app.task(name="workers.execute_task")
def execute_task(task_id: int) -> list[int]:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = TaskExecutionService(uow)
        task_case_ids = service.expand_task(task_id)
        uow.commit()

    for task_case_id in task_case_ids:
        run_task_case.delay(task_case_id)
    return task_case_ids


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


@celery_app.task(name="workers.run_task_case")
def run_task_case(task_case_id: int) -> int | None:
    attempt_id = _run_async(_run_task_case_async(task_case_id))
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
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        service = RuleValidationService(uow)
        service.validate_attempt(attempt_id)
        uow.commit()
    quantify_risk.delay(attempt_id)


@celery_app.task(name="workers.quantify_risk")
def quantify_risk(attempt_id: int) -> None:
    report_id: int | None = None
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        RiskScoringService(uow).quantify_attempt(attempt_id)
        attempt = uow.task_attempts.get(attempt_id)
        task_case = uow.task_cases.get(attempt.task_case_id) if attempt else None
        if task_case is not None:
            report = ReportAutomationService(uow).trigger_if_task_complete(task_case.task_id)
            if report is not None and report.status == "queued":
                report_id = report.id
        uow.commit()

    if report_id is not None:
        generate_report.delay(report_id)


@celery_app.task(name="workers.generate_report")
def generate_report(report_id: int) -> None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        report = ReportService(uow).generate_report(report_id)
        AuditLogService(uow).record(
            actor="system",
            action="report.generate",
            resource_type="report",
            resource_id=report_id,
            after_data={
                "status": report.status if report else "unknown",
                "format": report.format if report else None,
            },
        )
        uow.commit()
