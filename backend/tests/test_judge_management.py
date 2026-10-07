from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    Benchmark,
    BenchmarkVersion,
    EvaluationTask,
    JudgeResult,
    ManualReview,
    RuleDefinition,
    RuleSet,
    RuleValidationResult,
    TaskAttempt,
    TaskCase,
    TestCase,
)
from app.schemas.requests import JudgeProfileCreateRequest, JudgeProfileUpdateRequest
from app.services.judge_management import JudgeManagementService
from app.services.uow import UnitOfWork


def test_judge_profile_crud_and_trust_summary() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        uow = UnitOfWork(session)
        service = JudgeManagementService(uow)

        profile = service.create_profile(
            JudgeProfileCreateRequest(
                name="规则 Judge",
                judge_type="rule",
                strategy="keyword",
                prompt_template="请判断",
                params={"temperature": 0},
            )
        )
        session.commit()
        assert profile.id is not None

        updated = service.update_profile(profile.id, JudgeProfileUpdateRequest(name="更新后的 Judge"))
        session.commit()
        assert updated is not None
        assert updated.name == "更新后的 Judge"

        benchmark = Benchmark(name="judge-bench", slug="judge-bench", source_type="local")
        session.add(benchmark)
        session.flush()
        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()
        test_case = TestCase(benchmark_version_id=version.id, external_id="case-1", prompt="测试", status="active")
        session.add(test_case)
        session.flush()
        task = EvaluationTask(
            name="judge-task",
            benchmark_version_id=version.id,
            risk_taxonomy_id=1,
            status="succeeded",
            total_cases=1,
            completed_cases=1,
        )
        session.add(task)
        session.flush()
        task_case = TaskCase(task_id=task.id, test_case_id=test_case.id, case_key="case-1:0", status="succeeded")
        session.add(task_case)
        session.flush()
        attempt = TaskAttempt(
            task_case_id=task_case.id,
            model_id=1,
            attempt_no=1,
            status="succeeded",
            output_text="这是一个攻击性输出",
        )
        session.add(attempt)
        session.flush()
        result = JudgeResult(
            task_attempt_id=attempt.id,
            judge_profile_id=profile.id,
            run_no=1,
            verdict="safe",
            confidence=0.8,
            trust_score=0.5,
            status="succeeded",
        )
        session.add(result)
        session.flush()

        rule_set = RuleSet(name="rules", version="v1")
        session.add(rule_set)
        session.flush()
        rule = RuleDefinition(
            rule_set_id=rule_set.id,
            code="attack-keyword",
            rule_type="keyword",
            severity="critical",
            definition={"keywords": ["攻击"]},
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
        session.add(
            ManualReview(
                task_attempt_id=attempt.id,
                judge_result_id=result.id,
                trigger_reason="rule_conflict",
                status="pending",
            )
        )
        session.commit()

        summary = service.get_trust_summary(task.id)
        assert summary is not None
        assert summary.average_trust_score == 0.5
        assert summary.low_trust_count == 1
        assert summary.rule_conflict_count == 1
        assert summary.manual_review_count == 1

        disabled = service.disable_profile(profile.id)
        session.commit()
        assert disabled is not None
        assert disabled.enabled is False
