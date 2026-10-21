import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import AttackTemplate, Benchmark, ModelRegistry, TestCase
from app.schemas.requests import EvaluationTaskCreateRequest
from app.services.domain import TaskService
from app.services.execution import TaskExecutionService
from app.services.uow import UnitOfWork


def _payload(**overrides):
    data = {
        "name": "seed-task",
        "seed_test_case_ids": [1],
        "model_bindings": [
            {"model_id": 1, "role": "target", "model_params": {}, "enabled": True}
        ],
        "attack_template_ids": [],
        "judge_profile_ids": [],
        "rule_set_ids": [],
        "execution": {
            "repeat": 1,
            "timeout_seconds": 120,
            "retry": {"max_attempts": 1, "backoff_seconds": 3},
            "concurrency": 1,
        },
        "priority": "normal",
    }
    data.update(overrides)
    return EvaluationTaskCreateRequest(**data)


def test_payload_requires_seed_or_benchmark() -> None:
    assert _payload().seed_test_case_ids == [1]
    with pytest.raises(ValidationError):
        _payload(seed_test_case_ids=[], benchmark_id=None)


def test_create_task_with_seed_ids() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        benchmark = Benchmark(name="b", slug="b", source_type="local")
        session.add(benchmark)
        session.flush()
        seeds = [
            TestCase(benchmark_id=benchmark.id, external_id="s1", prompt="问题1", status="active"),
            TestCase(benchmark_id=benchmark.id, external_id="s2", prompt="问题2", status="active"),
        ]
        model = ModelRegistry(
            name="m",
            provider="local",
            adapter_type="mock",
            base_url="http://mock.local",
            model_name="m",
            usage_scope="target",
        )
        session.add_all(seeds + [model])
        session.commit()

        service = TaskService(UnitOfWork(session))
        task = service.create_task(
            _payload(seed_test_case_ids=[seeds[0].id, seeds[1].id], model_bindings=[
                {"model_id": model.id, "role": "target", "model_params": {}, "enabled": True}
            ])
        )
        session.commit()

        assert task.benchmark_id is None
        assert task.config["seed_test_case_ids"] == [seeds[0].id, seeds[1].id]


def test_create_task_rejects_unknown_seed() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = TaskService(UnitOfWork(session))
        with pytest.raises(ValueError):
            service.create_task(_payload(seed_test_case_ids=[9999]))


def test_expand_task_uses_selected_seeds() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        benchmark = Benchmark(name="b2", slug="b2", source_type="local")
        session.add(benchmark)
        session.flush()
        seeds = [
            TestCase(benchmark_id=benchmark.id, external_id="x1", prompt="问题A", status="active"),
            TestCase(benchmark_id=benchmark.id, external_id="x2", prompt="问题B", status="active"),
        ]
        model = ModelRegistry(
            name="m2",
            provider="local",
            adapter_type="mock",
            base_url="http://mock.local",
            model_name="m2",
            usage_scope="target",
        )
        template = AttackTemplate(
            method_code="role_play",
            name="tpl",
            template_text="回答：{prompt}",
            variables=["prompt"],
            version="v1",
            status="active",
        )
        session.add_all(seeds + [model, template])
        session.commit()

        uow = UnitOfWork(session)
        task = TaskService(uow).create_task(
            _payload(
                seed_test_case_ids=[seeds[0].id, seeds[1].id],
                attack_template_ids=[template.id],
                model_bindings=[
                    {"model_id": model.id, "role": "target", "model_params": {}, "enabled": True}
                ],
            )
        )
        session.commit()

        case_ids = TaskExecutionService(uow).expand_task(task.id)
        session.commit()

        assert len(case_ids) == 2
        assert task.total_cases == 2
