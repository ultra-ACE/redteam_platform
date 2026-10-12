"""报告生成幂等性测试：同一份报告不允许被重复生成。"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Report, StoredFile
from app.schemas import ReportCreateRequest, ReportFormat
from app.services.reporting import ReportAutomationService, ReportService
from app.services.uow import UnitOfWork
from tests.test_statistics_and_report import _seed_task


def _new_report(session: Session, task_id: int) -> Report:
    service = ReportService(UnitOfWork(session))
    report = service.create_report(
        ReportCreateRequest(
            task_id=task_id,
            report_type="full",
            format=ReportFormat.md,
            include=["summary"],
            filters={},
        )
    )
    session.commit()
    return report


def test_generate_report_writes_once_for_repeated_calls(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _seed_task(session)
        report = _new_report(session, task_id)
        service = ReportService(UnitOfWork(session))

        first = service.generate_report(report.id, base_dir=tmp_path)
        second = service.generate_report(report.id, base_dir=tmp_path)
        third = service.generate_report(report.id, base_dir=tmp_path)
        session.commit()

        assert first is not None and first.status == "ready"
        assert second is not None and second.status == "ready"
        assert third is not None and third.status == "ready"
        # 关键断言：重复调用不再产生新的文件台账记录
        assert session.query(StoredFile).count() == 1
        assert session.query(Report).count() == 1


def test_report_already_generating_is_skipped(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _seed_task(session)
        report = _new_report(session, task_id)

        report.status = "generating"
        session.commit()

        result = ReportService(UnitOfWork(session)).generate_report(report.id, base_dir=tmp_path)
        session.commit()

        assert result is not None
        assert result.status == "generating"
        assert session.query(StoredFile).count() == 0


def test_ensure_auto_report_marks_only_first_creation() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _seed_task(session)
        uow = UnitOfWork(session)

        first, first_created = ReportAutomationService(uow).ensure_auto_report(task_id)
        session.commit()
        second, second_created = ReportAutomationService(uow).ensure_auto_report(task_id)
        session.commit()

        assert first is not None and first_created is True
        assert second is not None and second_created is False
        assert second.id == first.id
        assert session.query(Report).count() == 1
