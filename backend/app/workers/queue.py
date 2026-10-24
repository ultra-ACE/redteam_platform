import logging

from app.core.config import settings
from app.workers.tasks import (
    dispatch_pending_task,
    dispatch_recovery,
    dispatch_task,
    generate_report,
    run_task_case,
)

logger = logging.getLogger(__name__)


def enqueue_task(task_id: int) -> None:
    if settings.celery_task_always_eager:
        dispatch_task.apply(args=(task_id,))
        return
    try:
        dispatch_task.delay(task_id)
    except Exception:
        logger.exception("failed to enqueue task %s", task_id)


def enqueue_pending_task_cases(task_id: int) -> None:
    """resume / recovery 场景下只派发 pending 状态的用例。"""
    if settings.celery_task_always_eager:
        dispatch_pending_task.apply(args=(task_id,))
        return
    try:
        dispatch_pending_task.delay(task_id)
    except Exception:
        logger.exception("failed to enqueue pending cases for task %s", task_id)


def enqueue_task_case_ids(task_case_ids: list[int]) -> None:
    """把已经重置为 pending 的用例直接重新派发。"""
    if not task_case_ids:
        return
    if settings.celery_task_always_eager:
        for task_case_id in task_case_ids:
            run_task_case.apply(args=(task_case_id,))
        return
    try:
        for task_case_id in task_case_ids:
            run_task_case.delay(task_case_id)
    except Exception:
        logger.exception("failed to enqueue retry task cases %s", task_case_ids)


def enqueue_report(report_id: int) -> None:
    if settings.celery_task_always_eager:
        generate_report.apply(args=(report_id,))
        return
    try:
        generate_report.delay(report_id)
    except Exception:
        logger.exception("failed to enqueue report %s", report_id)


def enqueue_recovery() -> None:
    if settings.celery_task_always_eager:
        dispatch_recovery.apply()
        return
    try:
        dispatch_recovery.delay()
    except Exception:
        logger.exception("failed to enqueue recovery")
