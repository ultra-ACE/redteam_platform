from collections import Counter
from typing import Any

from app.db.models import BenchmarkRiskMapping, RiskAssessment, RiskCategory, RiskDimensionScore, RiskTaxonomy, TestCase, TestCaseRiskLabel
from app.schemas import (
    RiskAssessment as RiskAssessmentSchema,
    RiskCategory as RiskCategorySchema,
    RiskDimension,
    RiskMappingBatchResult,
    RiskMappingItem,
    RiskMappingStatus,
)
from app.services.base import BaseService


class RiskMappingService(BaseService):
    def list_taxonomies(self, page: int = 1, page_size: int = 20) -> list[RiskTaxonomy]:
        return self.uow.risk_taxonomies.list(page=page, page_size=page_size)

    def create_taxonomy(self, payload: Any) -> RiskTaxonomy:
        taxonomy = RiskTaxonomy(
            name=payload.name,
            version=payload.version,
            description=payload.description,
            is_default=payload.is_default,
            status="active",
        )
        return self.uow.risk_taxonomies.add(taxonomy)

    def list_categories(self, taxonomy_id: int) -> list[RiskCategorySchema]:
        return self.list_category_tree(taxonomy_id)

    def list_category_tree(self, taxonomy_id: int) -> list[RiskCategorySchema]:
        categories = self.uow.risk_categories.list(page=1, page_size=5000, taxonomy_id=taxonomy_id)
        nodes: dict[int, RiskCategorySchema] = {
            category.id: RiskCategorySchema(
                risk_category_id=category.id,
                taxonomy_id=category.taxonomy_id,
                parent_id=category.parent_id,
                code=category.code,
                name=category.name,
                definition=category.definition,
                severity_weight=category.severity_weight,
                children=[],
            )
            for category in categories
        }
        roots: list[RiskCategorySchema] = []
        for category in categories:
            node = nodes[category.id]
            if category.parent_id and category.parent_id in nodes:
                nodes[category.parent_id].children.append(node)
            else:
                roots.append(node)
        return roots

    def create_category(self, taxonomy_id: int, payload: Any) -> RiskCategorySchema:
        category = RiskCategory(
            taxonomy_id=taxonomy_id,
            parent_id=payload.parent_id,
            code=payload.code,
            name=payload.name,
            definition=payload.definition,
            severity_weight=payload.severity_weight,
            examples=payload.examples,
            sort_order=payload.sort_order,
        )
        self.uow.risk_categories.add(category)
        return RiskCategorySchema(
            risk_category_id=category.id,
            taxonomy_id=category.taxonomy_id,
            parent_id=category.parent_id,
            code=category.code,
            name=category.name,
            definition=category.definition,
            severity_weight=category.severity_weight,
            children=[],
        )

    def get_mapping_status(self, benchmark_version_id: int) -> RiskMappingStatus:
        cases = self.uow.test_cases.list(
            page=1,
            page_size=100000,
            benchmark_version_id=benchmark_version_id,
        )
        counts = Counter(case.source_label for case in cases if case.source_label)
        mappings = self.uow.benchmark_risk_mappings.list(
            page=1,
            page_size=100000,
            benchmark_version_id=benchmark_version_id,
        )
        mapping_by_label: dict[str, BenchmarkRiskMapping] = {}
        for mapping in mappings:
            mapping_by_label.setdefault(mapping.raw_label, mapping)

        items: list[RiskMappingItem] = []
        unresolved: list[str] = []
        mapped_count = 0
        for raw_label, count in sorted(counts.items()):
            mapping = mapping_by_label.get(raw_label)
            category = self.uow.risk_categories.get(mapping.risk_category_id) if mapping else None
            if category is not None:
                mapped_count += 1
                items.append(
                    RiskMappingItem(
                        raw_label=raw_label,
                        count=count,
                        mapped_category_id=category.id,
                        mapped_category_code=category.code,
                        mapped_category_name=category.name,
                        status="mapped",
                    )
                )
            else:
                unresolved.append(raw_label)
                items.append(RiskMappingItem(raw_label=raw_label, count=count, status="unmapped"))

        total = len(counts)
        return RiskMappingStatus(
            benchmark_version_id=benchmark_version_id,
            total_labels=total,
            mapped_labels=mapped_count,
            mapping_rate=round(mapped_count / total, 4) if total else 0.0,
            unresolved_labels=unresolved,
            items=items,
        )

    def batch_upsert_mappings(self, benchmark_version_id: int, mappings: list[Any]) -> RiskMappingBatchResult:
        created = 0
        updated = 0
        affected_labels: set[str] = set()

        for item in mappings:
            affected_labels.add(item.raw_label)
            existing = self.uow.benchmark_risk_mappings.list(
                page=1,
                page_size=1,
                benchmark_version_id=benchmark_version_id,
                raw_label=item.raw_label,
                risk_category_id=item.risk_category_id,
            )
            if existing:
                entity = existing[0]
                entity.mapping_type = item.mapping_type
                entity.confidence = item.confidence
                entity.mapping_note = item.mapping_note
                updated += 1
            else:
                self.uow.benchmark_risk_mappings.add(
                    BenchmarkRiskMapping(
                        benchmark_version_id=benchmark_version_id,
                        raw_label=item.raw_label,
                        risk_category_id=item.risk_category_id,
                        mapping_type=item.mapping_type,
                        confidence=item.confidence,
                        mapping_note=item.mapping_note,
                    )
                )
                created += 1

        self.uow.session.flush()
        for raw_label in affected_labels:
            self._apply_label_mapping(benchmark_version_id, raw_label)

        status = self.get_mapping_status(benchmark_version_id)
        return RiskMappingBatchResult(
            created_count=created,
            updated_count=updated,
            remaining_unresolved_count=len(status.unresolved_labels),
        )

    def get_assessment(self, attempt_id: int, score_version: str = "risk-v1") -> RiskAssessmentSchema | None:
        assessments = self.uow.risk_assessments.list(
            page=1,
            page_size=1,
            task_attempt_id=attempt_id,
            score_version=score_version,
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

    def _apply_label_mapping(self, benchmark_version_id: int, raw_label: str) -> None:
        cases = self.uow.test_cases.list(
            page=1,
            page_size=100000,
            benchmark_version_id=benchmark_version_id,
            source_label=raw_label,
        )
        mappings = self.uow.benchmark_risk_mappings.list(
            page=1,
            page_size=1000,
            benchmark_version_id=benchmark_version_id,
            raw_label=raw_label,
        )
        for test_case in cases:
            existing = self.uow.test_case_risk_labels.list(
                page=1,
                page_size=1000,
                test_case_id=test_case.id,
            )
            for label in existing:
                if label.label_source == "benchmark":
                    self.uow.test_case_risk_labels.delete(label)
            for mapping in mappings:
                self.uow.test_case_risk_labels.add(
                    TestCaseRiskLabel(
                        test_case_id=test_case.id,
                        risk_category_id=mapping.risk_category_id,
                        label_source="benchmark",
                        is_primary=True,
                        confidence=mapping.confidence,
                    )
                )
