"""Backfill automatic manual-review records for existing Judge results."""

import argparse

from app.db.session import SessionLocal
from app.services import ManualReviewService, UnitOfWork


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", type=int, default=None)
    args = parser.parse_args()

    with SessionLocal() as session:
        uow = UnitOfWork(session)
        summary = ManualReviewService(uow).backfill(task_id=args.task_id)
        session.commit()
    print(f"scanned={summary['scanned']} created={summary['created']}")


if __name__ == "__main__":
    main()
