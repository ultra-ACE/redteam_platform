from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Benchmark, BenchmarkVersion, RiskCategory, RiskTaxonomy, TestCase, TestCaseRiskLabel
from app.schemas.requests import RiskCategoryCreateRequest, RiskMapping, RiskTaxonomyCreateRequest
from app.services.risk_mapping import RiskMappingService
from app.services.uow import UnitOfWork


def test_risk_mapping_tree_and_batch_mapping() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        uow = UnitOfWork(session)
        service = RiskMappingService(uow)

        taxonomy = service.create_taxonomy(
            RiskTaxonomyCreateRequest(name="统一风险体系", version="v1", is_default=True)
        )
        parent = service.create_category(
            taxonomy.id,
            RiskCategoryCreateRequest(code="harmful", name="有害内容", severity_weight=50),
        )
        child = service.create_category(
            taxonomy.id,
            RiskCategoryCreateRequest(
                code="harmful.violence",
                name="暴力内容",
                parent_id=parent.risk_category_id,
                severity_weight=80,
            ),
        )
        session.commit()

        tree = service.list_category_tree(taxonomy.id)
        assert len(tree) == 1
        assert tree[0].children[0].code == "harmful.violence"

        benchmark = Benchmark(name="mapping-bench", slug="mapping-bench", source_type="local")
        session.add(benchmark)
        session.flush()
        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()
        session.add_all(
            [
                TestCase(
                    benchmark_version_id=version.id,
                    external_id="case-1",
                    prompt="测试1",
                    source_label="violence",
                    status="active",
                ),
                TestCase(
                    benchmark_version_id=version.id,
                    external_id="case-2",
                    prompt="测试2",
                    source_label="unknown",
                    status="active",
                ),
            ]
        )
        session.commit()

        status = service.get_mapping_status(version.id)
        assert status.total_labels == 2
        assert status.mapped_labels == 0
        assert set(status.unresolved_labels) == {"violence", "unknown"}

        result = service.batch_upsert_mappings(
            version.id,
            [
                RiskMapping(
                    raw_label="violence",
                    risk_category_id=child.risk_category_id,
                    mapping_type="manual",
                    confidence=1.0,
                )
            ],
        )
        session.commit()

        assert result.created_count == 1
        assert result.remaining_unresolved_count == 1

        updated = service.get_mapping_status(version.id)
        assert updated.mapped_labels == 1
        assert updated.unresolved_labels == ["unknown"]
        assert session.query(TestCaseRiskLabel).count() == 1
