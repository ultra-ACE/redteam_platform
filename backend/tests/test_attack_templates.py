import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.base import Base
from app.schemas.requests import AttackMethodCreateRequest, AttackTemplateCreateRequest, AttackTemplateVersionCreateRequest
from app.services.attack_templates import AttackTemplateService
from app.services.uow import UnitOfWork


def test_attack_template_validation_preview_and_versions() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        service = AttackTemplateService(UnitOfWork(session))
        method = service.create_method(
            AttackMethodCreateRequest(code="role_play", name="角色扮演", enabled=True)
        )
        template = service.create_template(
            AttackTemplateCreateRequest(
                attack_method_id=method.id,
                name="角色扮演模板",
                template_text="你现在扮演 {role}，请回答：{prompt}",
                variables=["role", "prompt"],
                version="v1",
                status="active",
            )
        )
        session.commit()

        validation = service.validate_template(template.template_text, template.variables or [])
        assert validation.valid is True
        assert set(validation.detected_variables) == {"role", "prompt"}

        preview = service.preview_text(template.template_text, template.variables or [], {"role": "安全助手"})
        assert preview.valid is False
        assert preview.missing_variables == ["prompt"]
        assert "安全助手" in preview.rendered_prompt

        version = service.create_version(
            template.id,
            AttackTemplateVersionCreateRequest(version="v2", status="draft"),
        )
        session.commit()
        assert version is not None
        assert version.version == "v2"

        published = service.publish_version(version.id)
        session.commit()
        assert published is not None
        assert published.status == "active"
        refreshed = service.get_template(template.id)
        assert refreshed is not None
        assert refreshed.status == "disabled"


def test_attack_template_rejects_undeclared_variable() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        service = AttackTemplateService(UnitOfWork(session))
        method = service.create_method(
            AttackMethodCreateRequest(code="test_method", name="测试方法", enabled=True)
        )
        with pytest.raises(ValueError):
            service.create_template(
                AttackTemplateCreateRequest(
                    attack_method_id=method.id,
                    name="错误模板",
                    template_text="请回答：{unknown_variable}",
                    variables=[],
                    version="v1",
                )
            )
