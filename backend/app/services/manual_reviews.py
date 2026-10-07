from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import JudgeResult, ManualReview, RiskAssessment, RuleValidationResult, TaskAttempt, TaskCase, TestCase
from app.schemas import ManualReviewDetail
from app.services.base import BaseService


class ManualReviewService(BaseService):
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

    def get_detail(self, review_id: int) -> ManualReviewDetail | None:
        review = self.uow.manual_reviews.get(review_id)
        if review is None:
            return None
        return self._build_detail(review)

    def create_or_update(self, payload: Any, reviewer: str = "local") -> ManualReviewDetail:
        review = self.uow.manual_reviews.list(
            page=1,
            page_size=1,
            task_attempt_id=payload.task_attempt_id,
            status="pending",
        )
        if review:
            entity = review[0]
        else:
            entity = ManualReview(
                task_attempt_id=payload.task_attempt_id,
                trigger_reason=payload.trigger_reason,
                status="pending",
            )
            self.uow.manual_reviews.add(entity)

        self._apply_review_values(entity, payload, reviewer)
        self.uow.session.flush()
        return self._build_detail(entity)

    def update_review(self, review_id: int, payload: Any, reviewer: str = "local") -> ManualReviewDetail | None:
        entity = self.uow.manual_reviews.get(review_id)
        if entity is None:
            return None
        self._apply_review_values(entity, payload, reviewer)
        self.uow.session.flush()
        return self._build_detail(entity)

    def _apply_review_values(self, entity: ManualReview, payload: Any, reviewer: str) -> None:
        decision = payload.decision.value if hasattr(payload.decision, "value") else payload.decision
        entity.decision = decision
        entity.corrected_category_id = payload.corrected_category_id
        entity.corrected_score = payload.corrected_score
        entity.comment = payload.comment
        entity.reviewer = reviewer
        if decision in {"confirmed", "override"}:
            entity.status = "resolved"
        elif decision == "rejected":
            entity.status = "rejected"
        else:
            entity.status = "pending"
        payload_status = getattr(payload, "status", None)
        if payload_status:
            entity.status = payload_status
        entity.reviewed_at = datetime.now(timezone.utc)
        if decision == "override":
            self._apply_override(entity)

    def _apply_override(self, review: ManualReview) -> None:
        assessment = None
        if review.risk_assessment_id:
            assessment = self.uow.risk_assessments.get(review.risk_assessment_id)
        if assessment is None:
            assessments = self.uow.risk_assessments.list(
                page=1,
                page_size=1,
                task_attempt_id=review.task_attempt_id,
                order_by=RiskAssessment.id.desc(),
            )
            assessment = assessments[0] if assessments else None
        if assessment is not None and review.original_score is None:
            review.original_score = assessment.overall_score
        if assessment is not None and review.corrected_score is not None:
            assessment.overall_score = review.corrected_score
            assessment.risk_level = self._risk_level(review.corrected_score)
            assessment.confidence = 1.0
            assessment.uncertainty = 0.0
            review.risk_assessment_id = assessment.id

        if review.corrected_category_id:
            judge_results = self.uow.judge_results.list(
                page=1,
                page_size=1,
                task_attempt_id=review.task_attempt_id,
                order_by=JudgeResult.id.desc(),
            )
            if judge_results:
                judge_results[0].risk_category_id = review.corrected_category_id

    def _build_detail(self, review: ManualReview) -> ManualReviewDetail:
        attempt = self.uow.task_attempts.get(review.task_attempt_id)
        task_case = self.uow.task_cases.get(attempt.task_case_id) if attempt else None
        test_case = self.uow.test_cases.get(task_case.test_case_id) if task_case else None

        judge_result = None
        risk = None
        rules: list[RuleValidationResult] = []
        if attempt is not None:
            judge_results = self.uow.judge_results.list(
                page=1,
                page_size=1,
                task_attempt_id=attempt.id,
                order_by=JudgeResult.id.desc(),
            )
            judge_result = judge_results[0] if judge_results else None
            assessments = self.uow.risk_assessments.list(
                page=1,
                page_size=1,
                task_attempt_id=attempt.id,
                order_by=RiskAssessment.id.desc(),
            )
            risk = assessments[0] if assessments else None
            rules = self.uow.rule_validation_results.list(
                page=1,
                page_size=100,
                task_attempt_id=attempt.id,
            )

        rule_hits = sum(item.hit_count for item in rules)
        severities = [item.severity for item in rules if item.severity and not item.passed]
        severity_order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        highest_severity = max(severities, key=lambda value: severity_order.get(value, 0)) if severities else None

        return ManualReviewDetail(
            review_id=review.id,
            task_attempt_id=review.task_attempt_id,
            trigger_reason=review.trigger_reason,
            status=review.status,
            decision=review.decision,
            corrected_category_id=review.corrected_category_id,
            original_score=review.original_score if review.original_score is not None else (risk.overall_score if risk else None),
            corrected_score=review.corrected_score,
            comment=review.comment,
            reviewer=review.reviewer,
            reviewed_at=review.reviewed_at,
            task_id=task_case.task_id if task_case else None,
            test_case_id=test_case.id if test_case else None,
            external_id=test_case.external_id if test_case else None,
            prompt=test_case.prompt if test_case else None,
            model_output=attempt.output_text if attempt else None,
            judge_verdict=judge_result.verdict if judge_result else None,
            judge_confidence=judge_result.confidence if judge_result else None,
            judge_trust_score=judge_result.trust_score if judge_result else None,
            rule_hits=rule_hits,
            rule_highest_severity=highest_severity,
            original_risk_score=review.original_score if review.original_score is not None else (risk.overall_score if risk else None),
            original_risk_level=risk.risk_level if risk else None,
        )

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 40:
            return "medium"
        if score >= 20:
            return "low"
        return "info"
