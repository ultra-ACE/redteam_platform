"""Worker 启动时的断点续跑恢复。

后端或 Worker 重启后，扫描所有未完成的评测任务：

- ``pending`` 用例重新入队；
- heartbeat 超时的 ``running`` 用例重新置为 ``pending``（并累加 retry_count）；
- ``succeeded`` / ``cancelled`` 用例不再执行。

调用方：
    - ``celery_app.worker_ready`` 信号在 Worker 启动时自动触发；
    - 也可以通过 ``dispatch_recovery`` 任务手动触发。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import EvaluationTask, TaskCase
from app.db.session import SessionLocal
from app.services.execution import TaskExecutionService
from app.services.uow import UnitOfWork

logger = logging.getLogger(__name__)

#: running 用例超过该时长未更新心跳，则视为已失联
HEARTBEAT_TIMEOUT_SECONDS = 180
#: 未完成任务的状态
ACTIVE_TASK_STATUSES = ("queued", "running", "paused")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _heartbeat_deadline() -> datetime:
    return _now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)


def recover_incomplete_tasks() -> dict[str, int]:
    """扫描未完成任务并恢复。

    返回统计信息：``scanned_tasks`` / ``recovered_pending`` / ``reset_running``。
    """
    summary = {"scanned_tasks": 0, "recovered_pending": 0, "reset_running": 0, "pending_case_ids": []}

    with SessionLocal() as session:
        uow = UnitOfWork(session)
        deadline = _heartbeat_deadline()
        tasks = list(
            session.scalars(
                select(EvaluationTask).where(EvaluationTask.status.in_(ACTIVE_TASK_STATUSES))
            ).all()
        )

        for task in tasks:
            summary["scanned_tasks"] += 1
            task_cases = list(
                session.scalars(
                    select(TaskCase).where(TaskCase.task_id == task.id)
                ).all()
            )
            task_has_pending = False
            for task_case in task_cases:
                # 失联的 running 用例回滚为 pending
                if task_case.status == "running":
                    heartbeat = task_case.last_heartbeat_at
                    if heartbeat is None or heartbeat < deadline:
                        task_case.status = "pending"
                        task_case.retry_count = (task_case.retry_count or 0) + 1
                        task_case.celery_task_id = None
                        summary["reset_running"] += 1

                if task_case.status == "pending":
                    task_has_pending = True
                    summary["pending_case_ids"].append(task_case.id)

            uow.session.flush()

            if not task_has_pending:
                # 没有可恢复的用例（用例都已有结论，只是主任务状态没收尾：
                # 比如用例在暂停/停机期间跑完），这里补一次收尾，避免任务停在
                # queued/running，进度和完成数也不再更新。
                TaskExecutionService(uow).refresh_task_state(task.id)

        uow.commit()

    summary["recovered_pending"] = len(summary["pending_case_ids"])
    logger.info("recovery summary: %s", {k: v for k, v in summary.items() if k != "pending_case_ids"})
    return summary


def dispatch_recovered_cases(pending_case_ids: list[int]) -> int:
    """把恢复出来的 pending 用例重新入队。返回派发数量。"""
    if not pending_case_ids:
        return 0
    from app.workers.tasks import run_task_case

    for task_case_id in pending_case_ids:
        try:
            run_task_case.delay(task_case_id)
        except Exception:
            logger.exception("failed to enqueue recovered case %s", task_case_id)
    return len(pending_case_ids)