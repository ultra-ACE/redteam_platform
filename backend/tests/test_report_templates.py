from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Benchmark, BenchmarkVersion, EvaluationTask, ModelRegistry, TaskCase, TestCase
from app.schemas.requests import ReportCreateRequest, ReportTemplateCreateRequest, ReportTemplateVersionCreateRequest
from app.services.reporting import ReportAutomationService, ReportService, ReportTemplateService
from app.services.uow import UnitOfWork


def _seed_complete_task(session: Session) -> int:
    benchmark = Benchmark(name="template-bench", slug="template-bench", source_type="local")
    session.add(benchmark)
    session.flush()
    version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
    session.add(version)
    session.flush()
    test_case = TestCase(
        benchmark_version_id=version.id,
        external_id="template-case-1",
        prompt="测试",
        status="active",
    )
    model = ModelRegistry(
        name="template-model",
        provider="local",
        adapter_type="mock",
        base_url="http://mock.local",
        model_name="template-model",
        usage_scope="target",
    )
    session.add_all([test_case, model])
    session.flush()
    task = EvaluationTask(
        name="template-task",
        benchmark_version_id=version.id,
        risk_taxonomy_id=1,
        status="succeeded",
        total_cases=1,
        completed_cases=1,
        progress=1.0,
        config={},
    )
    session.add(task)
    session.flush()
    session.add(
        TaskCase(
            task_id=task.id,
            test_case_id=test_case.id,
            case_key="template-case-1:0",
            status="succeeded",
        )
    )
    session.commit()
    return task.id


def test_report_template_version_and_automation(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task_id = _seed_complete_task(session)
        uow = UnitOfWork(session)

        template_service = ReportTemplateService(uow)
        template = template_service.create_template(
            ReportTemplateCreateRequest(code="custom-json", name="Custom JSON")
        )
        version = template_service.create_version(
            template.id,
            ReportTemplateVersionCreateRequest(
                version="v1",
                format="json",
                content='{"task": {{ task.task_id }}, "total": {{ statistics.total_results }}}',
                variables_schema={},
                status="published",
            ),
        )
        session.commit()

        automation = ReportAutomationService(uow)
        auto_report = automation.trigger_if_task_complete(task_id, report_format="json")
        assert auto_report is not None
        assert auto_report.report_type == "auto"
        assert automation.trigger_if_task_complete(task_id, report_format="json").id == auto_report.id

        report = auto_report
        report.template_version_id = version.id
        session.commit()
        generated = ReportService(uow).generate_report(report.id, base_dir=tmp_path)
        assert generated is not None
        assert generated.status == "ready"
        output = (tmp_path / str(report.id) / f"report-{report.id}.json").read_text(encoding="utf-8")
        assert f'"task": {task_id}' in output
