from sqlalchemy import select

from app.db.models import (
    JudgeResult,
    ManualReview,
    RiskAssessment,
    RiskCategory,
    RuleValidationResult,
    TaskAttempt,
    TaskCase,
    TestCase,
    TestCaseRiskLabel,
)
from app.schemas import (
    EvaluationResult,
    JudgeSummary,
    PaginatedData,
    RiskCategoryRef,
    RiskSummary,
    RuleValidationSummary,
)
from app.services.base import BaseService


class EvaluationResultService(BaseService):
    def list_results(
        self,
        task_id: int,
        page: int = 1,
        page_size: int = 20,
        risk_level: str | None = None,
        needs_review: bool | None = None,
        model_id: int | None = None,
        attack_template_id: int | None = None,
        risk_category_code: str | None = None,
    ) -> PaginatedData[EvaluationResult]:
        items = self.list_all_results(
            task_id=task_id,
            risk_level=risk_level,
            needs_review=needs_review,
            model_id=model_id,
            attack_template_id=attack_template_id,
            risk_category_code=risk_category_code,
        )
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return PaginatedData[EvaluationResult](
            items=items[start:end],
            page=page,
            page_size=page_size,
            total=total,
            has_next=end < total,
        )

    def list_all_results(
        self,
        task_id: int,
        risk_level: str | None = None,
        needs_review: bool | None = None,
        model_id: int | None = None,
        attack_template_id: int | None = None,
        risk_category_code: str | None = None,
    ) -> list[EvaluationResult]:
        stmt = (
            select(TaskAttempt, TaskCase, TestCase)
            .join(TaskCase, TaskAttempt.task_case_id == TaskCase.id)
            .join(TestCase, TaskCase.test_case_id == TestCase.id)
            .where(TaskCase.task_id == task_id)
            .order_by(TaskAttempt.id.desc())
        )
        rows = self.uow.session.execute(stmt).all()
        items = [self._build_result(attempt, task_case, test_case) for attempt, task_case, test_case in rows]
        return self._apply_filters(
            items,
            risk_level=risk_level,
            needs_review=needs_review,
            model_id=model_id,
            attack_template_id=attack_template_id,
            risk_category_code=risk_category_code,
        )

    def _build_result(
        self,
        attempt: TaskAttempt,
        task_case: TaskCase,
        test_case: TestCase,
    ) -> EvaluationResult:
        judge_result = self._latest_judge_result(attempt.id)
        risk_assessment = self._latest_risk_assessment(attempt.id)
        rule_results = self.uow.rule_validation_results.list(
            page=1,
            page_size=1000,
            task_attempt_id=attempt.id,
        )
        manual_review = self._latest_manual_review(attempt.id)
        categories = self._risk_categories(judge_result, test_case.id)

        judge_summary = None
        if judge_result is not None:
            judge_summary = JudgeSummary(
                verdict=judge_result.verdict or "uncertain",
                confidence=judge_result.confidence or 0.0,
                trust_score=judge_result.trust_score or 0.0,
            )

        rule_summary = RuleValidationSummary(
            hit_count=sum(item.hit_count for item in rule_results),
            highest_severity=self._highest_severity(rule_results),
        )
        risk_summary = None
        if risk_assessment is not None:
            risk_summary = RiskSummary(
                overall_score=risk_assessment.overall_score,
                risk_level=risk_assessment.risk_level,
                confidence=risk_assessment.confidence,
                needs_review=(manual_review is not None and manual_review.status == "pending"),
            )

        return EvaluationResult(
            attempt_id=attempt.id,
            task_case_id=task_case.id,
            test_case_id=test_case.id,
            external_id=test_case.external_id,
            model_id=attempt.model_id,
            attack_template_id=task_case.attack_template_id,
            status=attempt.status,
            model_output_excerpt=(attempt.output_text or "")[:500],
            normalized_risk_categories=categories,
            judge=judge_summary,
            rule_validation=rule_summary,
            risk=risk_summary,
            manual_review_status=manual_review.status if manual_review else "none",
        )

    def _latest_judge_result(self, attempt_id: int) -> JudgeResult | None:
        results = self.uow.judge_results.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            status="succeeded",
            order_by=JudgeResult.id.desc(),
        )
        return results[0] if results else None

    def _latest_risk_assessment(self, attempt_id: int) -> RiskAssessment | None:
        results = self.uow.risk_assessments.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            order_by=RiskAssessment.id.desc(),
        )
        return results[0] if results else None

    def _latest_manual_review(self, attempt_id: int) -> ManualReview | None:
        reviews = self.uow.manual_reviews.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            order_by=ManualReview.id.desc(),
        )
        return reviews[0] if reviews else None

    def _risk_categories(self, judge_result: JudgeResult | None, test_case_id: int) -> list[RiskCategoryRef]:
        categories: list[RiskCategoryRef] = []
        if judge_result is not None and judge_result.risk_category_id:
            category = self.uow.risk_categories.get(judge_result.risk_category_id)
            if category is not None:
                categories.append(RiskCategoryRef(code=category.code, name=category.name))
                return categories

        labels = self.uow.test_case_risk_labels.list(
            page=1,
            page_size=100,
            test_case_id=test_case_id,
        )
        for label in labels:
            category = self.uow.risk_categories.get(label.risk_category_id)
            if category is not None:
                categories.append(RiskCategoryRef(code=category.code, name=category.name))
        return categories

    def _highest_severity(self, rule_results: list[RuleValidationResult]) -> str | None:
        order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        severities = [item.severity for item in rule_results if item.severity and not item.passed]
        if not severities:
            return None
        return max(severities, key=lambda value: order.get(value, 0))

    def _apply_filters(self, items: list[EvaluationResult], **filters) -> list[EvaluationResult]:
        risk_level = filters.get("risk_level")
        needs_review = filters.get("needs_review")
        model_id = filters.get("model_id")
        attack_template_id = filters.get("attack_template_id")
        risk_category_code = filters.get("risk_category_code")

        def match(item: EvaluationResult) -> bool:
            if risk_level and (item.risk is None or item.risk.risk_level != risk_level):
                return False
            if needs_review is not None and (item.risk is None or item.risk.needs_review != needs_review):
                return False
            if model_id is not None and item.model_id != model_id:
                return False
            if attack_template_id is not None and item.attack_template_id != attack_template_id:
                return False
            if risk_category_code and not any(
                category.code == risk_category_code for category in item.normalized_risk_categories
            ):
                return False
            return True

        return [item for item in items if match(item)]
