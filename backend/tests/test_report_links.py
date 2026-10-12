from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base
from app.schemas import ReportCreateRequest, ReportFormat
from app.services.reporting import ReportService
from app.services.uow import UnitOfWork
from tests.test_statistics_and_report import _seed_task

EXTENSIONS = {"md": "md", "html": "html", "csv": "csv", "pdf": "pdf"}


def _generate_report(tmp_path: Path, report_format: ReportFormat) -> tuple[int, int, bytes]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _seed_task(session)
        service = ReportService(UnitOfWork(session))
        report = service.create_report(
            ReportCreateRequest(
                task_id=task_id,
                report_type="full",
                format=report_format,
                include=["summary", "case_details"],
                filters={},
            )
        )
        session.commit()
        generated = service.generate_report(report.id, base_dir=tmp_path)
        assert generated is not None
        assert generated.status == "ready", generated.error_message
        path = tmp_path / str(report.id) / f"report-{report.id}.{EXTENSIONS[report_format.value]}"
        return task_id, report.id, path.read_bytes()


def test_markdown_report_links_attempt_to_attempt_detail(tmp_path) -> None:
    task_id, _, content = _generate_report(tmp_path, ReportFormat.md)
    text = content.decode("utf-8")
    expected = f"[1]({settings.frontend_base_url}/tasks/{task_id}?attempt=1)"

    assert "## 高风险案例 Top 10" in text
    assert "## 逐条结果摘要" in text
    assert text.count(expected) == 2


def test_html_report_contains_anchor_links(tmp_path) -> None:
    task_id, _, content = _generate_report(tmp_path, ReportFormat.html)
    text = content.decode("utf-8")
    expected = f'<a href="{settings.frontend_base_url}/tasks/{task_id}?attempt=1">1</a>'

    assert expected in text
    assert "高风险案例 Top 10" in text


def test_csv_report_exposes_detail_url_column(tmp_path) -> None:
    task_id, _, content = _generate_report(tmp_path, ReportFormat.csv)
    text = content.decode("utf-8-sig")

    assert "detail_url" in text
    assert f"{settings.frontend_base_url}/tasks/{task_id}?attempt=1" in text


def test_pdf_report_renders_clickable_attempt_links(tmp_path) -> None:
    _, _, content = _generate_report(tmp_path, ReportFormat.pdf)
    assert content.startswith(b"%PDF")
    # reportlab 会把 <link href> 写成 PDF 的 /URI 注释对象
    assert b"/URI" in content
