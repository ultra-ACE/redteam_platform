"""Recalculate trust scores for existing Judge results.

Usage:
    python scripts/recalculate_judge_trust.py [task_id]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.models import JudgeResult, TaskAttempt, TaskCase
from app.db.session import SessionLocal
from app.services.judge_eval import JudgeEvaluationService
from app.services.uow import UnitOfWork


def main() -> int:
    task_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        stmt = select(JudgeResult.task_attempt_id).distinct()
        if task_id is not None:
            stmt = (
                stmt.join(TaskAttempt, JudgeResult.task_attempt_id == TaskAttempt.id)
                .join(TaskCase, TaskAttempt.task_case_id == TaskCase.id)
                .where(TaskCase.task_id == task_id)
            )
        attempt_ids = list(session.scalars(stmt).all())
        service = JudgeEvaluationService(uow)
        result_count = 0
        for attempt_id in attempt_ids:
            result_count += len(service.recalculate_trust_scores(attempt_id))
        uow.commit()

    scope = f"task {task_id}" if task_id is not None else "all tasks"
    print(f"recalculated {result_count} Judge result(s) across {len(attempt_ids)} attempt(s) for {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
