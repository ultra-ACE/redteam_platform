import math

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    Benchmark,
    EvaluationTask,
    JudgeProfile,
    JudgeResult,
    RuleDefinition,
    RuleSet,
    RuleValidationResult,
    TaskAttempt,
    TaskCase,
    TestCase,
)
from app.services.judge_eval import JudgeEvaluationService
from app.services.uow import UnitOfWork


def test_recalculate_judge_trust_uses_rules_evidence_and_peer_agreement() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        benchmark = Benchmark(name="trust", slug="trust", source_type="local")
        session.add(benchmark)
        session.flush()
        test_case = TestCase(
            benchmark_id=benchmark.id,
            external_id="trust-case",
            prompt="test",
        )
        task = EvaluationTask(name="trust-task", benchmark_id=benchmark.id, status="running")
        session.add_all([test_case, task])
        session.flush()
        task_case = TaskCase(
            task_id=task.id,
            test_case_id=test_case.id,
            case_key="trust",
            status="succeeded",
        )
        session.add(task_case)
        session.flush()
        attempt = TaskAttempt(
            task_case_id=task_case.id,
            model_id=1,
            attempt_no=1,
            status="succeeded",
            output_text="unsafe output",
        )
        rule_profile = JudgeProfile(
            name="rule",
            judge_type="rule",
            strategy="keyword",
            enabled=True,
        )
        model_profile = JudgeProfile(
            name="model",
            judge_type="model",
            strategy="single",
            enabled=True,
        )
        session.add_all([attempt, rule_profile, model_profile])
        session.flush()
        safe_result = JudgeResult(
            task_attempt_id=attempt.id,
            judge_profile_id=rule_profile.id,
            run_no=1,
            verdict="safe",
            confidence=0.8,
            reasoning="safe reason",
            evidence=[{"quote": "safe"}],
            raw_output='{"verdict":"safe"}',
            status="succeeded",
        )
        unsafe_result = JudgeResult(
            task_attempt_id=attempt.id,
            judge_profile_id=model_profile.id,
            run_no=1,
            verdict="unsafe",
            confidence=0.9,
            reasoning="unsafe reason",
            evidence=[{"quote": "unsafe"}],
            raw_output='{"verdict":"unsafe"}',
            status="succeeded",
        )
        rule_set = RuleSet(name="trust-rules", version="v1")
        session.add_all([safe_result, unsafe_result, rule_set])
        session.flush()
        rule = RuleDefinition(
            rule_set_id=rule_set.id,
            code="critical-hit",
            rule_type="keyword",
            severity="critical",
            definition={"keywords": ["unsafe"]},
        )
        session.add(rule)
        session.flush()
        session.add(
            RuleValidationResult(
                task_attempt_id=attempt.id,
                rule_definition_id=rule.id,
                passed=False,
                severity="critical",
                hit_count=1,
            )
        )
        session.commit()

        service = JudgeEvaluationService(UnitOfWork(session))
        service.recalculate_trust_scores(attempt.id)
        session.commit()

        assert safe_result.trust_breakdown == {
            "rule_consistency": 0.0,
            "evidence_completeness": 1.0,
            "calibration_score": 0.0,
        }
        assert unsafe_result.trust_breakdown == {
            "rule_consistency": 1.0,
            "evidence_completeness": 1.0,
            "calibration_score": 0.0,
        }
        assert math.isclose(safe_result.trust_score, 1 / 3, rel_tol=1e-4)
        assert math.isclose(unsafe_result.trust_score, 2 / 3, rel_tol=1e-4)
