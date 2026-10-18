from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import ModelRegistry
from app.schemas.domain import Model, mask_secret_ref
from app.services.domain import ModelService
from app.services.uow import UnitOfWork


def _new_model(secret_ref: str) -> ModelRegistry:
    return ModelRegistry(
        name="secret-model",
        provider="local",
        adapter_type="mock",
        base_url="http://mock.local",
        model_name="secret-model",
        secret_ref=secret_ref,
        usage_scope="target",
        enabled=True,
    )


def test_mask_secret_ref_variants() -> None:
    assert mask_secret_ref(None) is None
    assert mask_secret_ref("") is None
    assert mask_secret_ref("env:DEEPSEEK_API_KEY") == "env:DEEPSEEK_API_KEY"
    assert mask_secret_ref("literal:sk-abcdefgh1234") == "literal:****1234"
    assert mask_secret_ref("sk-abcdefgh1234") == "****1234"
    assert mask_secret_ref("literal:abc") == "literal:****"


def test_model_response_never_returns_plaintext_secret() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        model = _new_model("literal:sk-secret-value-9876")
        session.add(model)
        session.commit()

        payload = Model.model_validate(model).model_dump()
        assert payload["secret_ref"] == "literal:****9876"
        assert payload["secret_configured"] is True
        assert "sk-secret-value" not in str(payload)


def test_update_model_ignores_masked_secret() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        model = _new_model("literal:sk-secret-value-9876")
        session.add(model)
        session.commit()

        service = ModelService(UnitOfWork(session))
        service.update_model(model.id, SimpleNamespace(secret_ref="literal:****9876"))
        session.commit()
        assert model.secret_ref == "literal:sk-secret-value-9876"

        service.update_model(model.id, SimpleNamespace(secret_ref="literal:new-key-4321"))
        session.commit()
        assert model.secret_ref == "literal:new-key-4321"
