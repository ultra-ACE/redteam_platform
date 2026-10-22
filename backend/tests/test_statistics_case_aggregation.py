from types import SimpleNamespace

from app.services.statistics import StatisticsService


class _ModelRepository:
    @staticmethod
    def get(model_id):
        return SimpleNamespace(name=f"model-{model_id}")


def _item(
    *,
    task_case_id: int,
    attempt_id: int,
    attempt_no: int,
    round_no: int | None,
    verdict: str | None,
):
    return SimpleNamespace(
        task_case_id=task_case_id,
        attempt_id=attempt_id,
        attempt_no=attempt_no,
        round_no=round_no,
        external_id=f"case-{task_case_id}",
        model_id=1,
        attack_template_id=1,
        dataset_type="harmful",
        sample_kind="seed",
        judge=(
            SimpleNamespace(verdict=verdict, trust_score=0.8, confidence=0.9)
            if verdict is not None
            else None
        ),
        rule_validation=SimpleNamespace(hit_count=1 if verdict == "unsafe" else 0),
        manual_review_status="pending" if verdict == "unsafe" else "none",
    )


def test_statistics_count_one_result_per_task_case() -> None:
    items = [
        _item(task_case_id=1, attempt_id=1, attempt_no=1, round_no=1, verdict="safe"),
        _item(task_case_id=1, attempt_id=2, attempt_no=2, round_no=2, verdict="unsafe"),
        _item(task_case_id=1, attempt_id=3, attempt_no=3, round_no=3, verdict="safe"),
        _item(task_case_id=2, attempt_id=4, attempt_no=1, round_no=1, verdict="uncertain"),
    ]
    service = StatisticsService(
        SimpleNamespace(models=_ModelRepository()),
    )

    statistics = service._build_statistics(task_id=1, items=items)

    assert statistics.total_results == 2
    assert statistics.safe_count == 0
    assert statistics.unsafe_count == 1
    assert statistics.uncertain_count == 1
    assert statistics.attack_success_rate == 0.5
    assert len(statistics.top_unsafe_cases) == 1
