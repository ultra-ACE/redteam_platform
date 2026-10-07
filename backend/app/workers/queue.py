import logging

from app.core.config import settings
from app.workers.tasks import dispatch_failed_task, dispatch_task, generate_report

logger = logging.getLogger(__name__)


def enqueue_task(task_id: int) -> None:
    if settings.celery_task_always_eager:
        dispatch_task.apply(args=(task_id,))
        return
    try:
        dispatch_task.delay(task_id)
    except Exception:
        logger.exception("failed to enqueue task %s", task_id)


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
