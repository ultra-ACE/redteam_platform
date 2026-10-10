import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.api.deps as api_deps
import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    Benchmark,
    BenchmarkVersion,
    EvaluationTask,
    ModelRegistry,
    TaskAttempt,
    TaskCase,
    TaskModelBinding,
    TestCase,
)
from app.main import app
from app.services.execution import TaskExecutionService
from app.services.judge_eval import JudgeEvaluationService
from app.services.results import EvaluationResultService
from app.services.risk_scoring import RiskScoringService
from app.services.rules import RuleValidationService
from app.services.uow import UnitOfWork

PROMPT = "请输出一个安全的测试回复"


def _build_chain(session: Session) -> tuple[int, int]:
    """构造 Benchmark → 任务 → 执行 → Judge → 规则 → 风险量化的完整链路。"""
    benchmark = Benchmark(name="detail-bench", slug="detail-bench", source_type="local")
    session.add(benchmark)
    session.flush()

    version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
    session.add(version)
    session.flush()

    test_case = TestCase(
        benchmark_version_id=version.id,
        external_id="detail-case-001",
        prompt=PROMPT,
        status="active",
    )
    session.add(test_case)
    session.flush()

    model = ModelRegistry(
        name="detail-mock",
        provider="local",
        adapter_type="mock",
        base_url="http://mock.local",
        model_name="detail-mock-model",
        usage_scope="target",
    )
    session.add(model)
    session.flush()

    task = EvaluationTask(
        name="detail-task",
        benchmark_version_id=version.id,
        risk_taxonomy_id=1,
        status="queued",
        config={
            "attack_template_ids": [],
            "judge_profile_ids": [],
            "rule_set_ids": [],
            "scoring": {"score_version": "risk-v1", "weights": {}},
        },
    )
    session.add(task)
    session.flush()
    session.add(TaskModelBinding(task_id=task.id, model_id=model.id, role="target"))
    session.commit()

    uow = UnitOfWork(session)
    execution = TaskExecutionService(uow)
    task_case_ids = execution.expand_task(task.id)
    session.commit()

    attempt_id = asyncio.run(execution.run_task_case(task_case_ids[0]))
    assert attempt_id is not None
    JudgeEvaluationService(uow).evaluate_attempt(attempt_id)
    RuleValidationService(uow).validate_attempt(attempt_id)
    RiskScoringService(uow).quantify_attempt(attempt_id)
    session.commit()
    return task.id, attempt_id


def test_attempt_detail_returns_full_evidence_chain() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        task_id, attempt_id = _build_chain(session)

        detail = EvaluationResultService(UnitOfWork(session)).get_attempt_detail(attempt_id)

        assert detail is not None
        assert detail.attempt_id == attempt_id
        assert detail.task_id == task_id
        assert detail.external_id == "detail-case-001"
        assert detail.prompt == PROMPT
        assert detail.model_output is not None and detail.model_output != ""
        assert detail.model_name == "detail-mock"

        assert detail.judge is not None
        assert detail.judge.judge_profile_name == "默认规则Judge"
        assert detail.judge.judge_type == "rule"
        assert detail.judge.verdict in {"safe", "unsafe", "uncertain"}

        assert len(detail.rule_validations) >= 2
        assert all(item.rule_code for item in detail.rule_validations)

        assert detail.risk is not None
        dimension_codes = {item.dimension_code for item in detail.risk.dimensions}
        assert dimension_codes == {
            "harm_severity",
            "attack_success",
            "intent_compliance",
            "rule_violation_severity",
            "multi_run_consistency",
            "cross_template_consistency",
        }


def test_attempt_detail_returns_none_for_unknown_id() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert EvaluationResultService(UnitOfWork(session)).get_attempt_detail(999) is None


def test_result_list_exposes_prompt_excerpt() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        task_id, _ = _build_chain(session)
        page = EvaluationResultService(UnitOfWork(session)).list_results(task_id)

        assert page.total == 1
        assert page.items[0].prompt_excerpt == PROMPT


def test_attempt_detail_endpoint(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'attempt-detail.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with testing_session() as session:
        benchmark = Benchmark(name="api-bench", slug="api-bench", source_type="local")
        session.add(benchmark)
        session.flush()
        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()
        test_case = TestCase(
            benchmark_version_id=version.id,
            external_id="api-case-001",
            prompt=PROMPT,
            status="active",
        )
        session.add(test_case)
        session.flush()
        task = EvaluationTask(
            name="api-task",
            benchmark_version_id=version.id,
            risk_taxonomy_id=1,
            status="succeeded",
            total_cases=1,
            completed_cases=1,
        )
        session.add(task)
        session.flush()
        task_case = TaskCase(
            task_id=task.id,
            test_case_id=test_case.id,
            case_key="api-case-001:0",
            status="succeeded",
        )
        session.add(task_case)
        session.flush()
        attempt = TaskAttempt(
            task_case_id=task_case.id,
            model_id=1,
            attempt_no=1,
            status="succeeded",
            output_text="模型输出",
        )
        session.add(attempt)
        session.commit()
        attempt_id = attempt.id

    monkeypatch.setattr(api_deps, "SessionLocal", testing_session)
    client = TestClient(app)

    response = client.get(f"/api/v1/task-attempts/{attempt_id}")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["attempt_id"] == attempt_id
    assert payload["prompt"] == PROMPT
    assert payload["model_output"] == "模型输出"

    missing = client.get("/api/v1/task-attempts/999999")
    assert missing.status_code == 404
