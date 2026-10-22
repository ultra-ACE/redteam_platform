from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import JudgeResult, ManualReview, RuleValidationResult, TaskAttempt, TaskCase
from app.schemas import ManualReviewDetail
from app.services.base import BaseService


class ManualReviewService(BaseService):
    LOW_CONFIDENCE_THRESHOLD = 0.65
    HIGH_RULE_SEVERITIES = {"high", "critical"}

    def list_reviews(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        trigger_reason: str | None = None,
        task_id: int | None = None,
        task_attempt_id: int | None = None,
    ) -> tuple[list[ManualReview], int]:
        stmt = select(ManualReview)
        if status:
            stmt = stmt.where(ManualReview.status == status)
        if trigger_reason:
            stmt = stmt.where(ManualReview.trigger_reason == trigger_reason)
        if task_attempt_id:
            stmt = stmt.where(ManualReview.task_attempt_id == task_attempt_id)
        if task_id:
            stmt = (
                stmt.join(TaskAttempt, ManualReview.task_attempt_id == TaskAttempt.id)
                .join(TaskCase, TaskAttempt.task_case_id == TaskCase.id)
                .where(TaskCase.task_id == task_id)
            )
        total = int(self.uow.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        items = list(
            self.uow.session.scalars(
                stmt.order_by(ManualReview.id.desc()).offset((page - 1) * page_size).limit(page_size)
            ).all()
        )
        return items, total

    def get_review(self, review_id: int) -> ManualReview | None:
        return self.uow.manual_reviews.get(review_id)

    def ensure_for_attempt(self, attempt_id: int) -> ManualReview | None:
        """Create one pending review when Judge/rules indicate uncertainty."""
        attempt = self.uow.task_attempts.get(attempt_id)
        if attempt is None:
            return None

        existing = self.uow.manual_reviews.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            status="pending",
        )
        if existing:
            return existing[0]

        judge_results = self.uow.judge_results.list(
            page=1,
            page_size=100,
            task_attempt_id=attempt_id,
            status="succeeded",
            order_by=JudgeResult.id,
        )
        if not judge_results:
            return None
        rules = self.uow.rule_validation_results.list(
            page=1,
            page_size=100,
            task_attempt_id=attempt_id,
        )
        trigger_reason, judge_result = self._determine_trigger(judge_results, rules)
        if trigger_reason is None or judge_result is None:
            return None

        review = ManualReview(
            task_attempt_id=attempt_id,
            judge_result_id=judge_result.id,
            trigger_reason=trigger_reason,
            status="pending",
        )
        self.uow.manual_reviews.add(review)
        self.uow.session.flush()
        return review

    def backfill(self, task_id: int | None = None) -> dict[str, int]:
        stmt = select(TaskAttempt.id).join(
            TaskCase,
            TaskAttempt.task_case_id == TaskCase.id,
        )
        if task_id is not None:
            stmt = stmt.where(TaskCase.task_id == task_id)
        attempt_ids = list(self.uow.session.scalars(stmt).all())
        created = 0
        for attempt_id in attempt_ids:
            before = self.uow.manual_reviews.count(
                task_attempt_id=attempt_id,
                status="pending",
            )
            review = self.ensure_for_attempt(attempt_id)
            if review is not None and before == 0:
                created += 1
        self.uow.session.flush()
        return {"scanned": len(attempt_ids), "created": created}

    def get_detail(self, review_id: int) -> ManualReviewDetail | None:
        review = self.uow.manual_reviews.get(review_id)
        return self._build_detail(review) if review else None

    def create_or_update(self, payload: Any, reviewer: str = "local") -> ManualReviewDetail:
        existing = self.uow.manual_reviews.list(
            page=1,
            page_size=1,
            task_attempt_id=payload.task_attempt_id,
            status="pending",
        )
        entity = existing[0] if existing else ManualReview(
            task_attempt_id=payload.task_attempt_id,
            trigger_reason=payload.trigger_reason,
            status="pending",
        )
        if not existing:
            self.uow.manual_reviews.add(entity)
        self._apply_values(entity, payload, reviewer)
        self.uow.session.flush()
        return self._build_detail(entity)

    def update_review(self, review_id: int, payload: Any, reviewer: str = "local") -> ManualReviewDetail | None:
        entity = self.uow.manual_reviews.get(review_id)
        if entity is None:
            return None
        self._apply_values(entity, payload, reviewer)
        self.uow.session.flush()
        return self._build_detail(entity)

    def _apply_values(self, entity: ManualReview, payload: Any, reviewer: str) -> None:
        decision = payload.decision.value if hasattr(payload.decision, "value") else payload.decision
        entity.decision = decision
        entity.corrected_verdict = getattr(payload, "corrected_verdict", None)
        entity.comment = payload.comment
        entity.reviewer = reviewer
        entity.status = "resolved" if decision in {"confirmed", "override"} else "rejected" if decision == "rejected" else "pending"
        if getattr(payload, "status", None):
            entity.status = payload.status
        entity.reviewed_at = datetime.now(timezone.utc)

    def _determine_trigger(
        self,
        judge_results: list[JudgeResult],
        rules: list[RuleValidationResult],
    ) -> tuple[str | None, JudgeResult | None]:
        failed_high_rules = [
            rule
            for rule in rules
            if not rule.passed and rule.severity in self.HIGH_RULE_SEVERITIES
        ]
        safe_results = [result for result in judge_results if result.verdict == "safe"]
        unsafe_results = [result for result in judge_results if result.verdict == "unsafe"]

        if failed_high_rules and safe_results:
            return "rule_conflict", safe_results[0]
        if rules and all(rule.passed for rule in rules) and unsafe_results:
            return "rule_conflict", unsafe_results[0]

        verdicts = {result.verdict for result in judge_results if result.verdict}
        if len(verdicts) > 1:
            return "judge_category_conflict", judge_results[0]

        uncertain = next(
            (result for result in judge_results if result.verdict == "uncertain"),
            None,
        )
        low_confidence = min(
            judge_results,
            key=lambda result: result.confidence
            if result.confidence is not None
            else 0.0,
        )
        if uncertain is not None or (
            low_confidence.confidence is not None
            and low_confidence.confidence < self.LOW_CONFIDENCE_THRESHOLD
        ):
            return "judge_low_trust", uncertain or low_confidence
        return None, None

    def _build_detail(self, review: ManualReview) -> ManualReviewDetail:
        attempt = self.uow.task_attempts.get(review.task_attempt_id)
        task_case = self.uow.task_cases.get(attempt.task_case_id) if attempt else None
        test_case = self.uow.test_cases.get(task_case.test_case_id) if task_case else None
        rendered_prompt = (
            str((attempt.input_snapshot or {}).get("prompt"))
            if attempt is not None and (attempt.input_snapshot or {}).get("prompt")
            else (test_case.prompt if test_case else None)
        )

        judge_result = None
        rules: list[RuleValidationResult] = []
        if attempt is not None:
            judge_results = self.uow.judge_results.list(
                page=1,
                page_size=1,
                task_attempt_id=attempt.id,
                order_by=JudgeResult.id.desc(),
            )
            judge_result = judge_results[0] if judge_results else None
            rules = self.uow.rule_validation_results.list(
                page=1,
                page_size=100,
                task_attempt_id=attempt.id,
            )

        severity_order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        severities = [item.severity for item in rules if item.severity and not item.passed]
        highest_severity = max(severities, key=lambda value: severity_order.get(value, 0)) if severities else None

        return ManualReviewDetail(
            review_id=review.id,
            task_attempt_id=review.task_attempt_id,
            trigger_reason=review.trigger_reason,
            status=review.status,
            decision=review.decision,
            corrected_verdict=review.corrected_verdict,
            comment=review.comment,
            reviewer=review.reviewer,
            reviewed_at=review.reviewed_at,
            task_id=task_case.task_id if task_case else None,
            test_case_id=test_case.id if test_case else None,
            external_id=test_case.external_id if test_case else None,
            prompt=rendered_prompt,
            model_output=attempt.output_text if attempt else None,
            judge_verdict=judge_result.verdict if judge_result else None,
            judge_confidence=judge_result.confidence if judge_result else None,
            judge_trust_score=judge_result.trust_score if judge_result else None,
            rule_hits=sum(item.hit_count for item in rules),
            rule_highest_severity=highest_severity,
        )
