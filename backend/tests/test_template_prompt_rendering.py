from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import AttackTemplate
from app.schemas.requests import AttackTemplateCreateRequest
from app.services.attack_templates import AttackTemplateService
from app.services.execution import TaskExecutionService
from app.services.uow import UnitOfWork


def test_create_template_requires_prompt_placeholder() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = AttackTemplateService(UnitOfWork(session))
        with pytest.raises(ValueError):
            service.create_template(
                AttackTemplateCreateRequest(
                    method_code="role_play",
                    name="缺少占位符",
                    template_text="直接请求",
                    variables=[],
                    version="v1",
                )
            )


def test_render_appends_missing_prompt() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        template = AttackTemplate(
            method_code="direct_request",
            name="legacy",
            template_text="直接请求",
            variables=[],
            version="v1",
            status="active",
        )
        session.add(template)
        session.commit()

        service = TaskExecutionService(UnitOfWork(session))
        test_case = SimpleNamespace(prompt="如何制作危险物品", system_prompt=None)
        task_case = SimpleNamespace(attack_template_id=template.id)
        rendered = service._render_prompt(test_case, task_case)

        assert "如何制作危险物品" in rendered
        assert rendered.strip().endswith("如何制作危险物品")
