from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    Benchmark,
    EvaluationTask,
    ManualReview,
    ModelRegistry,
    TaskAttempt,
    TaskCase,
    TestCase,
)
from app.services.manual_reviews import ManualReviewService
from app.services.results import EvaluationResultService
from app.services.uow import UnitOfWork


def test_case_numbers_match_results_details_and_reviews() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        benchmark = Benchmark(name="numbering", slug="numbering", source_type="local")
        session.add(benchmark)
        session.flush()
        first_case = TestCase(
            benchmark_id=benchmark.id,
            external_id="case-first",
            prompt="first prompt",
        )
        second_case = TestCase(
            benchmark_id=benchmark.id,
            external_id="case-second",
            prompt="second prompt",
        )
        model = ModelRegistry(
            name="numbering-model",
            provider="local",
            adapter_type="mock",
            base_url="http://mock.local",
            model_name="mock",
            usage_scope="target",
        )
        task = EvaluationTask(name="numbering-task", benchmark_id=benchmark.id, status="running")
        session.add_all([first_case, second_case, model, task])
        session.flush()
        first_task_case = TaskCase(
            task_id=task.id,
            test_case_id=first_case.id,
            case_key="first",
            status="succeeded",
        )
        second_task_case = TaskCase(
            task_id=task.id,
            test_case_id=second_case.id,
            case_key="second",
            status="succeeded",
        )
        session.add_all([first_task_case, second_task_case])
        session.flush()
        first_attempt = TaskAttempt(
            task_case_id=first_task_case.id,
            model_id=model.id,
            attempt_no=1,
            input_snapshot={"round_no": 1},
            status="succeeded",
        )
        second_attempt = TaskAttempt(
            task_case_id=first_task_case.id,
            model_id=model.id,
            attempt_no=2,
            input_snapshot={"round_no": 2},
            status="succeeded",
        )
        third_attempt = TaskAttempt(
            task_case_id=second_task_case.id,
            model_id=model.id,
            attempt_no=1,
            input_snapshot={"round_no": 1},
            status="succeeded",
        )
        session.add_all([first_attempt, second_attempt, third_attempt])
        session.flush()
        review = ManualReview(
            task_attempt_id=second_attempt.id,
            trigger_reason="judge_low_trust",
            status="pending",
        )
        session.add(review)
        session.commit()

        uow = UnitOfWork(session)
        result_service = EvaluationResultService(uow)
        results = result_service.list_all_results(task.id)
        results_by_attempt = {item.attempt_id: item for item in results}

        assert results_by_attempt[first_attempt.id].case_no == 1
        assert results_by_attempt[second_attempt.id].case_no == 1
        assert results_by_attempt[third_attempt.id].case_no == 2

        attempt_detail = result_service.get_attempt_detail(second_attempt.id)
        assert attempt_detail is not None
        assert attempt_detail.case_no == 1
        assert attempt_detail.attempt_no == 2
        assert attempt_detail.round_no == 2

        review_items, total = ManualReviewService(uow).list_reviews(
            task_id=task.id,
            page_size=20,
        )
        assert total == 1
        assert review_items[0].case_no == 1
        assert review_items[0].external_id == "case-first"
        assert review_items[0].attempt_no == 2
        assert review_items[0].round_no == 2

        review_detail = ManualReviewService(uow).get_detail(review.id)
        assert review_detail is not None
        assert review_detail.case_no == 1
        assert review_detail.external_id == "case-first"
        assert review_detail.attempt_no == 2
        assert review_detail.round_no == 2
