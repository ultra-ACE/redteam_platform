"""任务 SSE 事件流契约测试。"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.api.v1.routes.tasks as task_routes
import app.db.models  # noqa: F401
from app.db.base import Base
from app.main import app


def test_task_events_404_task_error(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(task_routes, "SessionLocal", testing_session)

    with TestClient(app).stream("GET", "/api/v1/evaluation-tasks/999999/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        first_line = None
        for line in response.iter_lines():
            if line:
                first_line = line
                break

    assert first_line is not None
    assert first_line.startswith("event: task_error")