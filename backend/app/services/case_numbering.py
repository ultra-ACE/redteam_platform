from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TaskCase


def case_number_map(session: Session, task_ids: Iterable[int]) -> dict[int, dict[int, int]]:
    """Return stable 1-based case numbers grouped by task."""
    normalized_ids = sorted({int(task_id) for task_id in task_ids})
    if not normalized_ids:
        return {}

    rows = session.execute(
        select(TaskCase.task_id, TaskCase.id)
        .where(TaskCase.task_id.in_(normalized_ids))
        .order_by(TaskCase.task_id, TaskCase.id)
    ).all()
    result: dict[int, dict[int, int]] = {task_id: {} for task_id in normalized_ids}
    for task_id, task_case_id in rows:
        result[task_id][task_case_id] = len(result[task_id]) + 1
    return result
