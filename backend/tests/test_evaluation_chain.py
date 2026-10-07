import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    Benchmark,
    BenchmarkVersion,
    EvaluationTask,
    ModelRegistry,
    TaskModelBinding,
    TestCase,
)
from app.services.execution import TaskExecutionService
from app.services.judge_eval import JudgeEvaluationService
from app.services.results import EvaluationResultService
from app.services.risk_scoring import RiskScoringService
from app.services.rules import RuleValidationService
from app.services.uow import UnitOfWork


def test_full_evaluation_chain() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        benchmark = Benchmark(name="chain-bench", slug="chain-bench", source_type="local")
        session.add(benchmark)
        session.flush()

        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()

        test_case = TestCase(
            benchmark_version_id=version.id,
            external_id="chain-case-001",
            prompt="请输出一个安全的测试回复",
            status="active",
        )
        session.add(test_case)
        session.flush()

        model = ModelRegistry(
            name="chain-mock",
            provider="local",
            adapter_type="mock",
            base_url="http://mock.local",
            model_name="chain-mock-model",
            usage_scope="target",
        )
        session.add(model)
        session.flush()

        task = EvaluationTask(
            name="chain-task",
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

        judges = JudgeEvaluationService(uow).evaluate_attempt(attempt_id)
        session.commit()
        assert len(judges) == 1
        assert judges[0].verdict == "safe"

        rules = RuleValidationService(uow).validate_attempt(attempt_id)
        session.commit()
        assert len(rules) >= 2
        assert any(result.passed for result in rules)

        assessment = RiskScoringService(uow).quantify_attempt(attempt_id)
        session.commit()
        assert assessment is not None
        assert 0 <= assessment.overall_score <= 100
        assert assessment.risk_level in {"info", "low", "medium", "high", "critical"}

        page = EvaluationResultService(uow).list_results(task.id)
        assert page.total == 1
        assert page.items[0].attempt_id == attempt_id
        assert page.items[0].judge is not None
        assert page.items[0].risk is not None
