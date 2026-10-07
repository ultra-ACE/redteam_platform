from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.api.deps as api_deps
import app.db.models  # noqa: F401
import app.services.audit as audit_service
from app.db.base import Base
from app.db.models import AuditLog
from app.main import app


def test_write_operation_creates_audit_log(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'audit-test.db'}",
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

    monkeypatch.setattr(api_deps, "SessionLocal", testing_session)
    monkeypatch.setattr(audit_service, "SessionLocal", testing_session)

    client = TestClient(app)
    response = client.patch(
        "/api/v1/system-configs/timeout",
        json={"config_value": 120},
        headers={"X-Operator": "tester", "X-Request-ID": "req_audit_test"},
    )

    assert response.status_code == 200
    assert response.json()["request_id"] == "req_audit_test"

    with testing_session() as session:
        log = session.query(AuditLog).filter(AuditLog.request_id == "req_audit_test").one()

    assert log.actor == "tester"
    assert log.action == "system_config.update"
    assert log.resource_type == "system_config"
    assert log.resource_id is None
    assert log.after_data["status_code"] == 200
    assert log.after_data["path"] == "/api/v1/system-configs/timeout"
def test_create_operation_uses_response_resource_id(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'audit-create-test.db'}",
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
    monkeypatch.setattr(api_deps, "SessionLocal", testing_session)
    monkeypatch.setattr(audit_service, "SessionLocal", testing_session)

    client = TestClient(app)
    response = client.post(
        "/api/v1/models",
        json={
            "name": "audit-model",
            "provider": "local",
            "adapter_type": "mock",
            "base_url": "http://127.0.0.1:9999",
            "model_name": "mock-model",
            "usage_scope": "target",
            "enabled": True,
        },
        headers={"X-Operator": "tester", "X-Request-ID": "req_audit_create_test"},
    )

    assert response.status_code == 200, response.text
    model_id = response.json()["data"]["model_id"]

    with testing_session() as session:
        log = session.query(AuditLog).filter(AuditLog.request_id == "req_audit_create_test").one()

    assert log.action == "model.create"
    assert log.resource_type == "model"
    assert log.resource_id == model_id
