from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Benchmark, BenchmarkVersion, RiskCategory, RiskTaxonomy, TestCase, TestCaseRiskLabel
from app.services.benchmark_import import BenchmarkImportService
from app.services.uow import UnitOfWork


def test_import_jsonl_benchmark(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        taxonomy = RiskTaxonomy(name="test-taxonomy", version="v1", is_default=True)
        session.add(taxonomy)
        session.flush()
        category = RiskCategory(
            taxonomy_id=taxonomy.id,
            code="harmful.violence",
            name="暴力内容",
            severity_weight=80,
        )
        session.add(category)
        session.commit()

        content = "\n".join(
            [
                '{"external_id":"case-1","prompt":"请输出危险内容","raw_label":"harmful.violence"}',
                '{"external_id":"case-2","prompt":"普通问题","raw_label":"unknown-label"}',
            ]
        ).encode("utf-8")

        result = BenchmarkImportService(UnitOfWork(session)).import_benchmark(
            name="Imported Benchmark",
            version="v1",
            content=content,
            file_name="cases.jsonl",
            mime_type="application/x-ndjson",
            risk_taxonomy_id=taxonomy.id,
            base_dir=tmp_path,
        )
        session.commit()

        assert result.imported_count == 2
        assert result.failed_count == 0
        assert result.unresolved_labels == ["unknown-label"]
        assert session.query(Benchmark).count() == 1
        assert session.query(BenchmarkVersion).count() == 1
        assert session.query(TestCase).count() == 2
        assert session.query(TestCaseRiskLabel).count() == 1


def test_import_csv_benchmark(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        content = "external_id,prompt,raw_label\ncase-1,测试问题,violence\n".encode("utf-8")
        result = BenchmarkImportService(UnitOfWork(session)).import_benchmark(
            name="CSV Benchmark",
            version="v1",
            content=content,
            file_name="cases.csv",
            mime_type="text/csv",
            base_dir=tmp_path,
        )
        session.commit()
        assert result.imported_count == 1
        assert result.unresolved_labels == ["violence"]
