import re
from typing import Any

from app.db.models import AttackMethod, AttackTemplate
from app.schemas import AttackTemplatePreviewResult, AttackTemplateValidationResult
from app.services.base import BaseService

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}|\{([A-Za-z_][A-Za-z0-9_.]*)\}")


class AttackTemplateService(BaseService):
    def list_methods(self, page: int = 1, page_size: int = 200, enabled: bool | None = None) -> list[AttackMethod]:
        return self.uow.attack_methods.list(page=page, page_size=page_size, enabled=enabled)

    def create_method(self, payload: Any) -> AttackMethod:
        method = AttackMethod(
            code=payload.code,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            risk_notes=payload.risk_notes,
            enabled=payload.enabled,
        )
        return self.uow.attack_methods.add(method)

    def update_method(self, method_id: int, payload: Any) -> AttackMethod | None:
        method = self.uow.attack_methods.get(method_id)
        if method is None:
            return None
        for field in ("name", "category", "description", "risk_notes", "enabled"):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(method, field, value)
        self.uow.session.flush()
        return method

    def disable_method(self, method_id: int) -> AttackMethod | None:
        method = self.uow.attack_methods.get(method_id)
        if method is None:
            return None
        method.enabled = False
        self.uow.session.flush()
        return method

    def list_templates(
        self,
        page: int = 1,
        page_size: int = 200,
        attack_method_id: int | None = None,
        name: str | None = None,
        status: str | None = None,
    ) -> list[AttackTemplate]:
        return self.uow.attack_templates.list(
            page=page,
            page_size=page_size,
            attack_method_id=attack_method_id,
            name=name,
            status=status,
        )

    def get_template(self, template_id: int) -> AttackTemplate | None:
        return self.uow.attack_templates.get(template_id)

    def create_template(self, payload: Any) -> AttackTemplate:
        self._ensure_unique_version(payload.attack_method_id, payload.name, payload.version)
        validation = self.validate_template(payload.template_text, payload.variables)
        if validation.undeclared_variables:
            raise ValueError(f"undeclared variables: {', '.join(validation.undeclared_variables)}")
        template = AttackTemplate(
            attack_method_id=payload.attack_method_id,
            name=payload.name,
            template_text=payload.template_text,
            variables=payload.variables,
            version=payload.version,
            status=payload.status,
        )
        return self.uow.attack_templates.add(template)

    def update_template(self, template_id: int, payload: Any) -> AttackTemplate | None:
        template = self.uow.attack_templates.get(template_id)
        if template is None:
            return None
        template_text = payload.template_text if payload.template_text is not None else template.template_text
        variables = payload.variables if payload.variables is not None else (template.variables or [])
        validation = self.validate_template(template_text, variables)
        if validation.undeclared_variables:
            raise ValueError(f"undeclared variables: {', '.join(validation.undeclared_variables)}")
        for field in ("name", "template_text", "variables", "status"):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(template, field, value)
        self.uow.session.flush()
        return template

    def disable_template(self, template_id: int) -> AttackTemplate | None:
        template = self.uow.attack_templates.get(template_id)
        if template is None:
            return None
        template.status = "disabled"
        self.uow.session.flush()
        return template

    def list_versions(self, template_id: int) -> list[AttackTemplate]:
        template = self.uow.attack_templates.get(template_id)
        if template is None:
            return []
        return self.uow.attack_templates.list(
            page=1,
            page_size=200,
            attack_method_id=template.attack_method_id,
            name=template.name,
        )

    def create_version(self, template_id: int, payload: Any) -> AttackTemplate | None:
        base = self.uow.attack_templates.get(template_id)
        if base is None:
            return None
        template_text = payload.template_text if payload.template_text is not None else base.template_text
        variables = payload.variables if payload.variables is not None else (base.variables or [])
        self._ensure_unique_version(base.attack_method_id, base.name, payload.version)
        validation = self.validate_template(template_text, variables)
        if validation.undeclared_variables:
            raise ValueError(f"undeclared variables: {', '.join(validation.undeclared_variables)}")
        version = AttackTemplate(
            attack_method_id=base.attack_method_id,
            name=base.name,
            template_text=template_text,
            variables=variables,
            version=payload.version,
            status=payload.status,
        )
        return self.uow.attack_templates.add(version)

    def publish_version(self, template_id: int) -> AttackTemplate | None:
        template = self.uow.attack_templates.get(template_id)
        if template is None:
            return None
        versions = self.list_versions(template_id)
        for item in versions:
            item.status = "disabled"
        template.status = "active"
        self.uow.session.flush()
        return template

    def validate_template(self, template_text: str, declared_variables: list[str]) -> AttackTemplateValidationResult:
        detected = self._detect_variables(template_text)
        declared_set = set(item for item in declared_variables if item)
        detected_set = set(detected)
        return AttackTemplateValidationResult(
            valid=not (detected_set - declared_set),
            detected_variables=sorted(detected_set),
            missing_variables=[],
            unused_variables=sorted(declared_set - detected_set),
            undeclared_variables=sorted(detected_set - declared_set),
        )

    def preview_template(self, template_id: int, variables: dict[str, Any]) -> AttackTemplatePreviewResult | None:
        template = self.uow.attack_templates.get(template_id)
        if template is None:
            return None
        return self.preview_text(template.template_text, template.variables or [], variables)

    def preview_text(
        self,
        template_text: str,
        declared_variables: list[str],
        variables: dict[str, Any],
    ) -> AttackTemplatePreviewResult:
        detected = self._detect_variables(template_text)
        declared_set = set(declared_variables)
        detected_set = set(detected)
        provided_set = set(variables.keys())
        missing = sorted(detected_set - provided_set)
        unused = sorted(declared_set - detected_set)
        undeclared = sorted(detected_set - declared_set)
        rendered = template_text
        for name in detected:
            value = variables.get(name)
            if value is not None:
                rendered = rendered.replace(f"{{{{{name}}}}}", str(value))
                rendered = rendered.replace(f"{{{name}}}", str(value))
        return AttackTemplatePreviewResult(
            valid=not missing and not undeclared,
            detected_variables=sorted(detected_set),
            missing_variables=missing,
            unused_variables=unused,
            undeclared_variables=undeclared,
            rendered_prompt=rendered,
        )

    def _detect_variables(self, template_text: str) -> list[str]:
        detected: list[str] = []
        for match in VARIABLE_PATTERN.finditer(template_text):
            name = match.group(1) or match.group(2)
            if name and name not in detected:
                detected.append(name)
        return detected

    def _ensure_unique_version(self, attack_method_id: int, name: str, version: str) -> None:
        existing = self.uow.attack_templates.list(
            page=1,
            page_size=1,
            attack_method_id=attack_method_id,
            name=name,
            version=version,
        )
        if existing:
            raise ValueError(f"attack template version already exists: {name}/{version}")
