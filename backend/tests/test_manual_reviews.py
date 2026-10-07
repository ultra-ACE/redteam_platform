from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Benchmark, BenchmarkVersion, EvaluationTask, ManualReview, RiskAssessment, TaskAttempt, TaskCase, TestCase
from app.schemas.requests import ManualReviewCreateRequest
from app.services.manual_reviews import ManualReviewService
from app.services.uow import UnitOfWork


def test_manual_review_detail_and_override() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        benchmark = Benchmark(name="review-bench", slug="review-bench", source_type="local")
        session.add(benchmark)
        session.flush()
        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()
        test_case = TestCase(benchmark_version_id=version.id, external_id="review-case", prompt="测试 Prompt", status="active")
        session.add(test_case)
        session.flush()
        task = EvaluationTask(
            name="review-task",
            benchmark_version_id=version.id,
            risk_taxonomy_id=1,
            status="succeeded",
            total_cases=1,
            completed_cases=1,
        )
        session.add(task)
        session.flush()
        task_case = TaskCase(task_id=task.id, test_case_id=test_case.id, case_key="review-case:0", status="succeeded")
        session.add(task_case)
        session.flush()
        attempt = TaskAttempt(task_case_id=task_case.id, model_id=1, attempt_no=1, status="succeeded", output_text="模型输出")
        session.add(attempt)
        session.flush()
        assessment = RiskAssessment(
            task_attempt_id=attempt.id,
            overall_score=55.0,
            risk_level="medium",
            confidence=0.5,
            uncertainty=0.5,
            judge_trust_score=0.5,
            score_version="risk-v1",
        )
        session.add(assessment)
        session.flush()
        review = ManualReview(
            task_attempt_id=attempt.id,
            risk_assessment_id=assessment.id,
            trigger_reason="judge_low_trust",
            status="pending",
        )
        session.add(review)
        session.commit()

        service = ManualReviewService(UnitOfWork(session))
        items, total = service.list_reviews(status="pending")
        assert total == 1
        assert items[0].id == review.id

        detail = service.get_detail(review.id)
        assert detail is not None
        assert detail.prompt == "测试 Prompt"
        assert detail.model_output == "模型输出"
        assert detail.original_risk_score == 55.0

        result = service.create_or_update(
            ManualReviewCreateRequest(
                task_attempt_id=attempt.id,
                trigger_reason="judge_low_trust",
                decision="override",
                corrected_score=88,
                comment="人工修正",
            ),
            reviewer="reviewer_01",
        )
        session.commit()
        assert result.status == "resolved"
        assert result.corrected_score == 88

        updated_assessment = session.get(RiskAssessment, assessment.id)
        assert updated_assessment is not None
        assert updated_assessment.overall_score == 88
        assert updated_assessment.risk_level == "critical"

        history, history_total = service.list_reviews(task_attempt_id=attempt.id)
        assert history_total == 1
        assert history[0].decision == "override"
