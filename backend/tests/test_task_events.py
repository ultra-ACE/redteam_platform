from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.api.deps as api_deps
import app.api.v1.routes.tasks as task_routes
import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import Benchmark, BenchmarkVersion, EvaluationTask, RiskTaxonomy, TaskCase, TestCase
from app.main import app


def test_task_events_emit_terminal_snapshot(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'task-events.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with testing_session() as session:
        taxonomy = RiskTaxonomy(name="taxonomy", version="v1", is_default=True)
        benchmark = Benchmark(name="benchmark", slug="benchmark", source_type="local")
        session.add_all([taxonomy, benchmark])
        session.flush()
        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()
        session.add(
            EvaluationTask(
                name="terminal-task",
                benchmark_version_id=version.id,
                risk_taxonomy_id=taxonomy.id,
                status="succeeded",
                progress=1.0,
                total_cases=1,
                completed_cases=1,
                failed_cases=0,
                config={},
            )
        )
        session.commit()

    monkeypatch.setattr(task_routes, "SessionLocal", testing_session)
    client = TestClient(app)

    response = client.get("/api/v1/evaluation-tasks/1/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in response.text
    assert '"status": "succeeded"' in response.text


def test_task_events_report_missing_task(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'task-events-missing.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(task_routes, "SessionLocal", testing_session)

    response = TestClient(app).get("/api/v1/evaluation-tasks/999/events")
    assert response.status_code == 200
    assert "event: task_error" in response.text
    assert "TASK_NOT_FOUND" in response.text


def test_retry_failed_endpoint_dispatches_only_failed_cases(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'retry-failed-endpoint.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with testing_session() as session:
        taxonomy = RiskTaxonomy(name="retry-taxonomy", version="v1", is_default=True)
        benchmark = Benchmark(name="retry-bench", slug="retry-bench", source_type="local")
        session.add_all([taxonomy, benchmark])
        session.flush()
        version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1", status="ready")
        session.add(version)
        session.flush()
        test_case = TestCase(
            benchmark_version_id=version.id,
            external_id="case-001",
            prompt="case-001",
            status="active",
        )
        session.add(test_case)
        session.flush()
        task = EvaluationTask(
            name="retry-task",
            benchmark_version_id=version.id,
            risk_taxonomy_id=taxonomy.id,
            status="failed",
            total_cases=1,
            completed_cases=0,
            failed_cases=1,
            progress=1.0,
            config={},
        )
        session.add(task)
        session.flush()
        task_case = TaskCase(
            task_id=task.id,
            test_case_id=test_case.id,
            case_key="case-001:0:1",
            status="failed",
            case_config={"model_id": 1},
        )
        session.add(task_case)
        session.commit()
        task_id = task.id

    monkeypatch.setattr(api_deps, "SessionLocal", testing_session)
    monkeypatch.setattr(task_routes, "SessionLocal", testing_session)
    enqueued: list[int] = []
    monkeypatch.setattr(task_routes, "enqueue_failed_task_cases", lambda task_id: enqueued.append(task_id))

    response = TestClient(app).post(f"/api/v1/evaluation-tasks/{task_id}/actions/retry-failed")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["retry_count"] == 1
    assert payload["status"] == "queued"
    assert enqueued == [task_id]

    with testing_session() as session:
        refreshed_task = session.get(EvaluationTask, task_id)
        refreshed_case = session.get(TaskCase, task_case.id)
        assert refreshed_task is not None
        assert refreshed_task.status == "queued"
        assert refreshed_task.total_cases == 1
        assert refreshed_task.completed_cases == 0
        assert refreshed_task.failed_cases == 0
        assert refreshed_task.progress == 0.0
        assert refreshed_case is not None
        assert refreshed_case.status == "pending"
        assert refreshed_case.retry_count == 1
