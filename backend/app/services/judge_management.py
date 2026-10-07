from statistics import mean
from typing import Any

from sqlalchemy import func, select

from app.db.models import JudgeProfile, JudgeResult, ManualReview, RuleValidationResult, TaskAttempt, TaskCase
from app.schemas import JudgeTrustSummary
from app.services.base import BaseService
from app.services.judge_eval import JudgeEvaluationService


class JudgeManagementService(BaseService):
    def list_profiles(
        self,
        page: int = 1,
        page_size: int = 200,
        judge_type: str | None = None,
        enabled: bool | None = None,
    ) -> list[JudgeProfile]:
        return self.uow.judge_profiles.list(
            page=page,
            page_size=page_size,
            judge_type=judge_type,
            enabled=enabled,
        )

    def create_profile(self, payload: Any) -> JudgeProfile:
        profile = JudgeProfile(
            name=payload.name,
            judge_type=payload.judge_type.value if hasattr(payload.judge_type, "value") else payload.judge_type,
            judge_model_id=payload.judge_model_id,
            strategy=payload.strategy,
            prompt_template=payload.prompt_template,
            params=payload.params,
            enabled=payload.enabled,
        )
        return self.uow.judge_profiles.add(profile)

    def get_profile(self, profile_id: int) -> JudgeProfile | None:
        return self.uow.judge_profiles.get(profile_id)

    def update_profile(self, profile_id: int, payload: Any) -> JudgeProfile | None:
        profile = self.uow.judge_profiles.get(profile_id)
        if profile is None:
            return None
        for field in ("name", "strategy", "prompt_template", "params", "enabled", "judge_model_id"):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(profile, field, value)
        judge_type = getattr(payload, "judge_type", None)
        if judge_type is not None:
            profile.judge_type = judge_type.value if hasattr(judge_type, "value") else judge_type
        self.uow.session.flush()
        return profile

    def disable_profile(self, profile_id: int) -> JudgeProfile | None:
        profile = self.uow.judge_profiles.get(profile_id)
        if profile is None:
            return None
        profile.enabled = False
        self.uow.session.flush()
        return profile

    def get_trust_summary(self, task_id: int) -> JudgeTrustSummary | None:
        task = self.uow.evaluation_tasks.get(task_id)
        if task is None:
            return None

        attempt_ids = list(
            self.uow.session.scalars(
                select(TaskAttempt.id)
                .join(TaskCase, TaskAttempt.task_case_id == TaskCase.id)
                .where(TaskCase.task_id == task_id)
            ).all()
        )
        if not attempt_ids:
            return JudgeTrustSummary(
                task_id=task_id,
                average_trust_score=0.0,
                low_trust_count=0,
                rule_conflict_count=0,
                manual_review_count=0,
            )

        judge_results = list(
            self.uow.session.scalars(
                select(JudgeResult).where(
                    JudgeResult.task_attempt_id.in_(attempt_ids),
                    JudgeResult.status == "succeeded",
                )
            ).all()
        )
        trust_scores = [item.trust_score for item in judge_results if item.trust_score is not None]
        low_trust_count = sum(1 for score in trust_scores if score < 0.65)
        rule_conflict_count = sum(1 for item in judge_results if self._has_rule_conflict(item))
        manual_review_count = int(
            self.uow.session.scalar(
                select(func.count()).select_from(ManualReview).where(ManualReview.task_attempt_id.in_(attempt_ids))
            )
            or 0
        )

        return JudgeTrustSummary(
            task_id=task_id,
            average_trust_score=round(mean(trust_scores), 4) if trust_scores else 0.0,
            low_trust_count=low_trust_count,
            rule_conflict_count=rule_conflict_count,
            manual_review_count=manual_review_count,
        )

    def re_evaluate(self, judge_result_id: int) -> JudgeResult | None:
        return JudgeEvaluationService(self.uow).re_evaluate(judge_result_id)

    def _has_rule_conflict(self, judge_result: JudgeResult) -> bool:
        rules = self.uow.rule_validation_results.list(
            page=1,
            page_size=100,
            task_attempt_id=judge_result.task_attempt_id,
        )
        high_severity = [rule for rule in rules if not rule.passed and rule.severity in {"high", "critical"}]
        if high_severity and judge_result.verdict == "safe":
            return True
        if rules and all(rule.passed for rule in rules) and judge_result.verdict == "unsafe":
            return True
        return False
