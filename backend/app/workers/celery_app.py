import logging
import os

from celery import Celery
from celery.signals import worker_ready

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "llm_eval",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_eager_propagates,
    # T8：提高 Worker 吞吐。CLI 的 --concurrency 仍可覆盖该值。
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "4")),
    worker_prefetch_multiplier=int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    task_default_queue="celery",
    task_routes={
        "workers.generate_report": {"queue": "reports"},
    },
)

celery_app.autodiscover_tasks(["app.workers"])


@worker_ready.connect
def _recover_incomplete_tasks_on_startup(sender=None, **kwargs) -> None:  # noqa: ARG001
    """Worker 启动时扫描未完成任务，恢复 pending 用例。"""
    try:
        from app.workers.tasks import dispatch_recovery
        dispatch_recovery.delay()
        logger.info("recovery dispatched on worker ready")
    except Exception:
        logger.exception("failed to dispatch recovery on worker ready")
