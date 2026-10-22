import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import JudgeProfile, ModelRegistry
from app.services.domain import ModelService
from app.services.uow import UnitOfWork


def _model() -> ModelRegistry:
    return ModelRegistry(
        name="delete-model",
        provider="local",
        adapter_type="mock",
        base_url="http://mock.local",
        model_name="mock",
        usage_scope="target",
    )


def test_delete_unused_model() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        model = _model()
        session.add(model)
        session.commit()

        service = ModelService(UnitOfWork(session))
        assert service.delete_model(model.id) is True
        session.commit()
        assert session.get(ModelRegistry, model.id) is None


def test_delete_model_rejects_judge_reference() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        model = _model()
        session.add(model)
        session.flush()
        session.add(
            JudgeProfile(
                name="judge",
                judge_type="model",
                judge_model_id=model.id,
                strategy="single",
                enabled=True,
            )
        )
        session.commit()

        service = ModelService(UnitOfWork(session))
        with pytest.raises(ValueError, match="Judge 配置"):
            service.delete_model(model.id)
