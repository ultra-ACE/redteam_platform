from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import EvaluationTask, ModelRegistry
from app.schemas.enums import ReportFormat
from app.services.attack_templates import AttackTemplateService
from app.services.domain import ModelService, TaskService
from app.services.uow import UnitOfWork


def test_removed_tables_are_not_part_of_metadata() -> None:
    removed = {
        "risk_taxonomies",
        "risk_categories",
        "risk_assessments",
        "risk_dimension_scores",
        "risk_label_aliases",
        "benchmark_risk_mappings",
        "test_case_risk_labels",
        "attack_methods",
        "task_events",
        "statistics_snapshots",
        "report_templates",
        "report_template_versions",
        "system_configs",
        "audit_logs",
    }
    assert removed.isdisjoint(Base.metadata.tables)


def test_contract_enums_and_fixed_attack_methods() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = AttackTemplateService(UnitOfWork(session))
        assert [item["code"] for item in service.list_methods()] == [
            "direct_request",
            "role_play",
            "prefix_injection",
            "refusal_suppression",
        ]
    assert [item.value for item in ReportFormat] == ["html"]


def test_task_pause_and_resume_contract() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        task = EvaluationTask(
            name="contract-task",
            benchmark_version_id=1,
            status="running",
            total_cases=1,
            config={},
            pause_requested=False,
        )
        session.add(task)
        session.commit()

        service = TaskService(UnitOfWork(session))
        paused = service.pause_task(task.id)
        session.commit()
        assert paused is not None
        assert paused.status == "paused"
        assert paused.pause_requested is True

        resumed = service.resume_task(task.id)
        session.commit()
        assert resumed is not None
        assert resumed.status == "queued"
        assert resumed.pause_requested is False


def test_model_update_contract() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        model = ModelRegistry(
            name="old-name",
            provider="local",
            adapter_type="mock",
            base_url="http://mock.local",
            model_name="mock",
            usage_scope="target",
            enabled=True,
        )
        session.add(model)
        session.commit()

        updated = ModelService(UnitOfWork(session)).update_model(
            model.id,
            SimpleNamespace(name="new-name", enabled=False),
        )
        session.commit()
        assert updated is not None
        assert updated.name == "new-name"
        assert updated.enabled is False
