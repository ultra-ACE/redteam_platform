import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.models import Benchmark, BenchmarkVersion, ModelRegistry, RiskTaxonomy, TestCase  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def get_or_create(session, model, defaults=None, **filters):
    stmt = select(model).filter_by(**filters)
    instance = session.scalar(stmt)
    if instance is not None:
        return instance
    params = {**filters, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    session.flush()
    return instance


def main() -> None:
    with SessionLocal() as session:
        taxonomy = get_or_create(
            session,
            RiskTaxonomy,
            name="demo-risk-taxonomy",
            version="v1",
            defaults={"description": "Demo taxonomy", "is_default": True},
        )
        benchmark = get_or_create(
            session,
            Benchmark,
            slug="demo-benchmark",
            defaults={"name": "Demo Benchmark", "source_type": "local", "status": "active"},
        )
        version = get_or_create(
            session,
            BenchmarkVersion,
            benchmark_id=benchmark.id,
            version="v1",
            defaults={"status": "ready", "case_count": 1},
        )
        test_case = get_or_create(
            session,
            TestCase,
            benchmark_version_id=version.id,
            external_id="demo-case-001",
            defaults={
                "prompt": "请输出一个安全的测试回复",
                "status": "active",
            },
        )
        model = get_or_create(
            session,
            ModelRegistry,
            name="demo-mock-model",
            model_name="mock-model-v1",
            defaults={
                "provider": "local",
                "adapter_type": "mock",
                "base_url": "http://mock.local",
                "usage_scope": "target",
                "enabled": True,
            },
        )
        session.commit()

        print("seed_ready")
        print(f"risk_taxonomy_id={taxonomy.id}")
        print(f"benchmark_id={benchmark.id}")
        print(f"benchmark_version_id={version.id}")
        print(f"test_case_id={test_case.id}")
        print(f"model_id={model.id}")


if __name__ == "__main__":
    main()
