from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import ModelRegistry
from app.services.uow import UnitOfWork


def test_domain_table_count() -> None:
    assert len(Base.metadata.tables) == 31


def test_unit_of_work_can_create_and_read_model() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        uow = UnitOfWork(session)
        uow.models.add(
            ModelRegistry(
                name="uow-test",
                provider="local",
                adapter_type="mock",
                base_url="http://127.0.0.1:9999",
                model_name="mock-model",
                usage_scope="target",
            )
        )
        session.commit()

        model = uow.models.get(1)
        assert model is not None
        assert model.name == "uow-test"
