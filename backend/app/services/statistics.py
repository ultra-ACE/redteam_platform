from datetime import datetime, timezone
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
        stats = self._build_statistics(task_id, items)

        if persist:
            self.uow.statistics_snapshots.add(
                self.uow.statistics_snapshots.model(
                    task_id=task_id,
                    scope="task",
                    metrics=stats.model_dump(mode="json"),
                    generated_at=datetime.now(timezone.utc),
                )
            )
            self.uow.session.flush()
        return stats

    def _build_statistics(self, task_id: int, items: list[EvaluationResult]) -> Statistics:
        total = len(items)
        safe = sum(1 for item in items if item.judge and item.judge.verdict == "safe")
        unsafe = sum(1 for item in items if item.judge and item.judge.verdict == "unsafe")
        uncertain = sum(1 for item in items if item.judge is None or item.judge.verdict == "uncertain")

        risk_scores = [item.risk.overall_score for item in items if item.risk is not None]
        judge_trust_scores = [item.judge.trust_score for item in items if item.judge is not None]
        judge_confidence_scores = [item.judge.confidence for item in items if item.judge is not None]
        reviewed = sum(1 for item in items if item.manual_review_status not in {"none", None})
        rule_hits = sum(
            1
            for item in items
            if item.rule_validation is not None and item.rule_validation.hit_count > 0
        )

        risk_levels: dict[str, int] = {}
        category_stats: dict[str, dict[str, float]] = {}
        model_stats: dict[int, dict[str, float]] = {}
        template_stats: dict[int, dict[str, float]] = {}

        for item in items:
            if item.risk is not None:
                risk_levels[item.risk.risk_level] = risk_levels.get(item.risk.risk_level, 0) + 1

            for category in item.normalized_risk_categories:
                current = category_stats.setdefault(category.code, {"count": 0.0, "total_score": 0.0})
                current["count"] += 1
                if item.risk is not None:
                    current["total_score"] += item.risk.overall_score

            model_current = model_stats.setdefault(item.model_id, {"count": 0.0, "risky": 0.0, "total_score": 0.0})
            model_current["count"] += 1
            if item.judge is not None and item.judge.verdict == "unsafe":
                model_current["risky"] += 1
            if item.risk is not None:
                model_current["total_score"] += item.risk.overall_score

            if item.attack_template_id is not None:
                template_current = template_stats.setdefault(
                    item.attack_template_id, {"count": 0.0, "risky": 0.0, "total_score": 0.0}
                )
                template_current["count"] += 1
                if item.judge is not None and item.judge.verdict == "unsafe":
                    template_current["risky"] += 1
                if item.risk is not None:
                    template_current["total_score"] += item.risk.overall_score

        top_cases = sorted(
            [item for item in items if item.risk is not None],
            key=lambda item: item.risk.overall_score,
            reverse=True,
        )[:10]

        model_breakdown = []
        for model_id, value in sorted(model_stats.items()):
            model = self.uow.models.get(model_id)
            model_breakdown.append(
                {
                    "model_id": model_id,
                    "model_name": model.name if model else None,
                    "count": int(value["count"]),
                    "unsafe_count": int(value["risky"]),
                    "attack_success_rate": round(value["risky"] / value["count"], 4) if value["count"] else 0.0,
                    "average_risk_score": round(value["total_score"] / value["count"], 2) if value["count"] else 0.0,
                }
            )

        return Statistics(
            task_id=task_id,
            total_results=total,
            safe_count=safe,
            unsafe_count=unsafe,
            uncertain_count=uncertain,
            high_risk_count=risk_levels.get("high", 0) + risk_levels.get("critical", 0),
            critical_risk_count=risk_levels.get("critical", 0),
            attack_success_rate=round(unsafe / total, 4) if total else 0.0,
            average_risk_score=round(mean(risk_scores), 2) if risk_scores else 0.0,
            average_judge_confidence=round(mean(judge_confidence_scores), 4) if judge_confidence_scores else 0.0,
            judge_average_trust=round(mean(judge_trust_scores), 4) if judge_trust_scores else 0.0,
            manual_review_rate=round(reviewed / total, 4) if total else 0.0,
            rule_hit_rate=round(rule_hits / total, 4) if total else 0.0,
            risk_level_distribution=risk_levels,
            risk_category_distribution=[
                {
                    "code": code,
                    "count": int(value["count"]),
                    "average_score": round(value["total_score"] / value["count"], 2) if value["count"] else 0.0,
                }
                for code, value in sorted(category_stats.items())
            ],
            model_breakdown=model_breakdown,
            attack_template_breakdown=[
                {
                    "attack_template_id": template_id,
                    "count": int(value["count"]),
                    "unsafe_count": int(value["risky"]),
                    "attack_success_rate": round(value["risky"] / value["count"], 4) if value["count"] else 0.0,
                    "average_risk_score": round(value["total_score"] / value["count"], 2) if value["count"] else 0.0,
                }
                for template_id, value in sorted(template_stats.items())
            ],
            top_risky_cases=[
                {
                    "attempt_id": item.attempt_id,
                    "external_id": item.external_id,
                    "model_id": item.model_id,
                    "attack_template_id": item.attack_template_id,
                    "overall_score": item.risk.overall_score,
                    "risk_level": item.risk.risk_level,
                }
                for item in top_cases
            ],
        )
