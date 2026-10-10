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
    AttemptDetail,
    EvaluationResult,
    JudgeDetail,
    JudgeSummary,
    ManualReview as ManualReviewSchema,
    PaginatedData,
    RiskAssessment as RiskAssessmentSchema,
    RiskCategoryRef,
    RiskDimension,
    RiskSummary,
    RuleValidationDetail,
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
            prompt_excerpt=(test_case.prompt or "")[:200],
            model_output_excerpt=(attempt.output_text or "")[:500],
            normalized_risk_categories=categories,
            judge=judge_summary,
            rule_validation=rule_summary,
            risk=risk_summary,
            manual_review_status=manual_review.status if manual_review else "none",
        )

    def get_attempt_detail(self, attempt_id: int) -> AttemptDetail | None:
        """组装单次尝试的完整证据链，供前端结果表格展开查看。"""
        attempt = self.uow.task_attempts.get(attempt_id)
        if attempt is None:
            return None

        task_case = self.uow.task_cases.get(attempt.task_case_id)
        test_case = self.uow.test_cases.get(task_case.test_case_id) if task_case else None
        model = self.uow.models.get(attempt.model_id)
        template = (
            self.uow.attack_templates.get(task_case.attack_template_id)
            if task_case is not None and task_case.attack_template_id
            else None
        )

        judge_result = self._latest_judge_result(attempt.id)
        manual_review = self._latest_manual_review(attempt.id)
        categories = self._risk_categories(judge_result, test_case.id if test_case else 0)

        return AttemptDetail(
            attempt_id=attempt.id,
            task_id=task_case.task_id if task_case else None,
            task_case_id=attempt.task_case_id,
            test_case_id=test_case.id if test_case else None,
            external_id=test_case.external_id if test_case else None,
            model_id=attempt.model_id,
            model_name=model.name if model else None,
            attack_template_id=task_case.attack_template_id if task_case else None,
            attack_template_name=template.name if template else None,
            attempt_no=attempt.attempt_no,
            status=attempt.status,
            prompt=test_case.prompt if test_case else None,
            system_prompt=test_case.system_prompt if test_case else None,
            input_snapshot=attempt.input_snapshot,
            model_output=attempt.output_text,
            latency_ms=attempt.latency_ms,
            prompt_tokens=attempt.prompt_tokens,
            completion_tokens=attempt.completion_tokens,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            normalized_risk_categories=categories,
            judge=self._build_judge_detail(judge_result),
            rule_validations=self._build_rule_details(attempt.id),
            risk=self._build_risk_detail(attempt.id),
            manual_review=ManualReviewSchema.model_validate(manual_review) if manual_review else None,
        )

    def _build_judge_detail(self, judge_result: JudgeResult | None) -> JudgeDetail | None:
        if judge_result is None:
            return None

        profile = self.uow.judge_profiles.get(judge_result.judge_profile_id)
        category = (
            self.uow.risk_categories.get(judge_result.risk_category_id)
            if judge_result.risk_category_id
            else None
        )

        return JudgeDetail(
            judge_result_id=judge_result.id,
            judge_profile_id=judge_result.judge_profile_id,
            judge_profile_name=profile.name if profile else None,
            judge_type=profile.judge_type if profile else None,
            strategy=profile.strategy if profile else None,
            verdict=judge_result.verdict or "uncertain",
            risk_category=RiskCategoryRef(code=category.code, name=category.name) if category else None,
            confidence=judge_result.confidence,
            trust_score=judge_result.trust_score,
            trust_breakdown=judge_result.trust_breakdown,
            reasoning=judge_result.reasoning,
            evidence=judge_result.evidence,
            raw_output=judge_result.raw_output,
        )

    def _build_rule_details(self, attempt_id: int) -> list[RuleValidationDetail]:
        rows = self.uow.rule_validation_results.list(
            page=1,
            page_size=1000,
            task_attempt_id=attempt_id,
        )
        details: list[RuleValidationDetail] = []
        for row in rows:
            definition = self.uow.rule_definitions.get(row.rule_definition_id)
            details.append(
                RuleValidationDetail(
                    rule_definition_id=row.rule_definition_id,
                    rule_code=definition.code if definition else None,
                    passed=row.passed,
                    severity=row.severity,
                    hit_count=row.hit_count,
                    matched_evidence=row.matched_evidence,
                )
            )
        return details

    def _build_risk_detail(self, attempt_id: int) -> RiskAssessmentSchema | None:
        assessments = self.uow.risk_assessments.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            order_by=RiskAssessment.id.desc(),
        )
        if not assessments:
            return None
        assessment = assessments[0]
        dimension_rows = self.uow.risk_dimension_scores.list(
            page=1,
            page_size=100,
            risk_assessment_id=assessment.id,
        )
        return RiskAssessmentSchema(
            attempt_id=assessment.task_attempt_id,
            overall_score=assessment.overall_score,
            risk_level=assessment.risk_level,
            confidence=assessment.confidence,
            uncertainty=assessment.uncertainty,
            judge_trust_score=assessment.judge_trust_score or 0.0,
            score_version=assessment.score_version,
            dimensions=[
                RiskDimension(
                    dimension_code=item.dimension_code,
                    score=item.score,
                    weight=item.weight,
                    source=item.source,
                    evidence=item.evidence,
                )
                for item in dimension_rows
            ],
            rule_override_applied=assessment.rule_override_applied,
            calculated_at=assessment.calculated_at,
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
