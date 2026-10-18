import logging

from app.core.config import settings
from app.workers.tasks import (
    dispatch_failed_task,
    dispatch_pending_task,
    dispatch_recovery,
    dispatch_task,
    generate_report,
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


def enqueue_failed_task_cases(task_id: int) -> None:
    if settings.celery_task_always_eager:
        dispatch_failed_task.apply(args=(task_id,))
        return
    try:
        dispatch_failed_task.delay(task_id)
    except Exception:
        logger.exception("failed to enqueue failed task cases %s", task_id)


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