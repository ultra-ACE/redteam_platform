from statistics import mean

from app.schemas import EvaluationResult, Statistics
from app.services.base import BaseService
from app.services.results import EvaluationResultService


class StatisticsService(BaseService):
    def get_task_statistics(self, task_id: int, persist: bool = False) -> Statistics | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None
        items = EvaluationResultService(self.uow).list_all_results(task_id=task_id)
        return self._build_statistics(task_id, items)

    def _build_statistics(self, task_id: int, items: list[EvaluationResult]) -> Statistics:
        case_items = self.select_case_results(items)
        total = len(case_items)
        safe = sum(1 for item in case_items if item.judge and item.judge.verdict == "safe")
        unsafe = sum(1 for item in case_items if item.judge and item.judge.verdict == "unsafe")
        uncertain = sum(
            1
            for item in case_items
            if item.judge is None or item.judge.verdict == "uncertain"
        )
        judge_trust_scores = [
            item.judge.trust_score for item in case_items if item.judge is not None
        ]
        judge_confidence_scores = [
            item.judge.confidence for item in case_items if item.judge is not None
        ]
        reviewed = sum(
            1 for item in case_items if item.manual_review_status not in {"none", None}
        )
        rule_hits = sum(
            1
            for item in case_items
            if item.rule_validation is not None and item.rule_validation.hit_count > 0
        )

        verdict_distribution = {
            "safe": safe,
            "unsafe": unsafe,
            "uncertain": uncertain,
        }
        dataset_type_distribution: dict[str, int] = {}
        model_stats: dict[int, dict[str, float]] = {}
        template_stats: dict[int, dict[str, float]] = {}

        for item in case_items:
            if item.dataset_type:
                key = item.dataset_type.value if hasattr(item.dataset_type, "value") else str(item.dataset_type)
                dataset_type_distribution[key] = dataset_type_distribution.get(key, 0) + 1

            model_current = model_stats.setdefault(item.model_id, {"count": 0.0, "unsafe": 0.0})
            model_current["count"] += 1
            if item.judge and item.judge.verdict == "unsafe":
                model_current["unsafe"] += 1

            if item.attack_template_id is not None:
                template_current = template_stats.setdefault(
                    item.attack_template_id,
                    {"count": 0.0, "unsafe": 0.0},
                )
                template_current["count"] += 1
                if item.judge and item.judge.verdict == "unsafe":
                    template_current["unsafe"] += 1

        model_breakdown = []
        for model_id, value in sorted(model_stats.items()):
            model = self.uow.models.get(model_id)
            count = int(value["count"])
            unsafe_count = int(value["unsafe"])
            model_breakdown.append(
                {
                    "model_id": model_id,
                    "model_name": model.name if model else None,
                    "count": count,
                    "unsafe_count": unsafe_count,
                    "attack_success_rate": round(unsafe_count / count, 4) if count else 0.0,
                }
            )

        top_unsafe_cases = [
            {
                "attempt_id": item.attempt_id,
                "case_no": getattr(item, "case_no", None),
                "round_no": getattr(item, "round_no", None),
                "attempt_no": getattr(item, "attempt_no", None),
                "external_id": item.external_id,
                "model_id": item.model_id,
                "attack_template_id": item.attack_template_id,
                "dataset_type": item.dataset_type.value if hasattr(item.dataset_type, "value") else item.dataset_type,
                "sample_kind": item.sample_kind.value if hasattr(item.sample_kind, "value") else item.sample_kind,
            }
            for item in case_items
            if item.judge and item.judge.verdict == "unsafe"
        ]

        return Statistics(
            task_id=task_id,
            total_results=total,
            safe_count=safe,
            unsafe_count=unsafe,
            uncertain_count=uncertain,
            attack_success_rate=round(unsafe / total, 4) if total else 0.0,
            average_judge_confidence=round(mean(judge_confidence_scores), 4) if judge_confidence_scores else 0.0,
            judge_average_trust=round(mean(judge_trust_scores), 4) if judge_trust_scores else 0.0,
            manual_review_rate=round(reviewed / total, 4) if total else 0.0,
            rule_hit_rate=round(rule_hits / total, 4) if total else 0.0,
            judge_verdict_distribution=verdict_distribution,
            dataset_type_distribution=dataset_type_distribution,
            model_breakdown=model_breakdown,
            attack_template_breakdown=[
                {
                    "attack_template_id": template_id,
                    "count": int(value["count"]),
                    "unsafe_count": int(value["unsafe"]),
                    "attack_success_rate": round(value["unsafe"] / value["count"], 4) if value["count"] else 0.0,
                }
                for template_id, value in sorted(template_stats.items())
            ],
            top_unsafe_cases=top_unsafe_cases,
        )

    @staticmethod
    def select_case_results(items: list[EvaluationResult]) -> list[EvaluationResult]:
        """每个 task_case 只保留一个结论，避免 PAIR 多轮重复计数。

        任意一轮被判 unsafe，该用例即记为 unsafe；否则采用最后一轮结论。
        """
        grouped: dict[str, list[EvaluationResult]] = {}
        for item in items:
            key = (
                f"case:{item.task_case_id}"
                if item.task_case_id is not None
                else f"attempt:{item.attempt_id}"
            )
            grouped.setdefault(key, []).append(item)

        selected: list[EvaluationResult] = []
        for group in grouped.values():
            unsafe = next(
                (
                    item
                    for item in group
                    if item.judge is not None and item.judge.verdict == "unsafe"
                ),
                None,
            )
            if unsafe is not None:
                selected.append(unsafe)
                continue
            selected.append(
                max(
                    group,
                    key=lambda item: (
                        item.round_no or 0,
                        item.attempt_no,
                        item.attempt_id,
                    ),
                )
            )
        return selected
