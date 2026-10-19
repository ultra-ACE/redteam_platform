from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.schemas.requests import JudgeProfileCreateRequest, JudgeProfileUpdateRequest
from app.services.judge_management import JudgeManagementService
from app.services.uow import UnitOfWork


def test_rule_judge_drops_model_binding() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        service = JudgeManagementService(UnitOfWork(session))
        profile = service.create_profile(
            JudgeProfileCreateRequest(
                name="rule-judge",
                judge_type="rule",
                judge_model_id=1,
                strategy="keyword",
            )
        )
        session.commit()
        assert profile.judge_type == "rule"
        assert profile.judge_model_id is None


def test_switching_to_rule_clears_model_binding() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        service = JudgeManagementService(UnitOfWork(session))
        profile = service.create_profile(
            JudgeProfileCreateRequest(
                name="model-judge",
                judge_type="model",
                judge_model_id=7,
                strategy="single",
            )
        )
        session.commit()
        assert profile.judge_model_id == 7

        updated = service.update_profile(
            profile.id,
            JudgeProfileUpdateRequest(judge_type="rule"),
        )
        session.commit()
        assert updated is not None
        assert updated.judge_type == "rule"
        assert updated.judge_model_id is None
