import re
from typing import Any

from app.db.models import AttackTemplate
from app.schemas import AttackTemplatePreviewResult, AttackTemplateValidationResult
from app.services.base import BaseService

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}|\{([A-Za-z_][A-Za-z0-9_.]*)\}")

ATTACK_METHODS = [
    {
        "code": "direct_request",
        "name": "直接请求",
        "description": "不套用模板，直接把原始 Prompt 发送给被测模型。",
    },
    {
        "code": "role_play",
        "name": "角色扮演",
        "description": "通过虚构角色或场景诱导模型绕过安全限制。",
    },
    {
        "code": "prefix_injection",
        "name": "前缀注入",
        "description": "在用户输入前后注入指令，改变模型的安全策略。",
    },
    {
        "code": "refusal_suppression",
        "name": "拒答抑制",
        "description": "要求模型不得拒绝回答，强制给出完整内容。",
    },
]


class AttackTemplateService(BaseService):
   
    def list_templates(
        self,
        page: int = 1,
        page_size: int = 200,
        method_code: str | None = None,
        name: str | None = None,
        status: str | None = None,
    ) -> list[AttackTemplate]:
        return self.uow.attack_templates.list(
            page=page,
            page_size=page_size,
            method_code=method_code,
            name=name,
            status=status,
        )
    def list_methods(self) -> list[dict[str, str]]:
        return ATTACK_METHODS
    def get_template(self, template_id: int) -> AttackTemplate | None:
        return self.uow.attack_templates.get(template_id)

    def create_template(self, payload: Any) -> AttackTemplate:
        method_code = payload.method_code.value if hasattr(payload.method_code, "value") else payload.method_code
        library_name = (payload.library_name or "默认模板库").strip() or "默认模板库"
        template_text = self._normalize_template_text(payload.template_text)
        self._ensure_unique_version(library_name, payload.name, payload.version)
        validation = self.validate_template(template_text, payload.variables)
        if validation.undeclared_variables:
            raise ValueError(f"undeclared variables: {', '.join(validation.undeclared_variables)}")
        template = AttackTemplate(
            library_name=library_name,
            method_code=method_code,
            name=payload.name,
            template_text=template_text,
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
        template_text = self._normalize_template_text(template_text)
        validation = self.validate_template(template_text, variables)
        if validation.undeclared_variables:
            raise ValueError(f"undeclared variables: {', '.join(validation.undeclared_variables)}")
        for field in ("library_name", "name", "template_text", "variables", "status"):
            value = getattr(payload, field, None)
            if value is not None:
                if field == "library_name":
                    value = str(value).strip() or "默认模板库"
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
            library_name=template.library_name,
            name=template.name,
        )

    def create_version(self, template_id: int, payload: Any) -> AttackTemplate | None:
        base = self.uow.attack_templates.get(template_id)
        if base is None:
            return None
        template_text = payload.template_text if payload.template_text is not None else base.template_text
        variables = payload.variables if payload.variables is not None else (base.variables or [])
        template_text = self._normalize_template_text(template_text)
        self._ensure_unique_version(base.library_name, base.name, payload.version)
        validation = self.validate_template(template_text, variables)
        if validation.undeclared_variables:
            raise ValueError(f"undeclared variables: {', '.join(validation.undeclared_variables)}")
        version = AttackTemplate(
            library_name=base.library_name,
            method_code=base.method_code,
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
        for item in self.list_versions(template_id):
            item.status = "disabled"
        template.status = "active"
        self.uow.session.flush()
        return template

    def validate_template(self, template_text: str, declared_variables: list[str]) -> AttackTemplateValidationResult:
        detected = self._detect_variables(template_text)
        declared_set = set(item for item in declared_variables if item)
        detected_set = set(detected)
        return AttackTemplateValidationResult(
            # 官方模板可能没有占位符，执行时会自动把种子拼到末尾
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

    def _ensure_unique_version(self, library_name: str, name: str, version: str) -> None:
        existing = self.uow.attack_templates.list(
            page=1,
            page_size=1,
            library_name=library_name,
            name=name,
            version=version,
        )
        if existing:
            raise ValueError(f"attack template version already exists: {name}/{version}")

    @staticmethod
    def _normalize_template_text(template_text: str) -> str:
        """兼容官方数据集里的占位符写法，统一成 {prompt}。"""
        normalized = template_text
        for alias in ("{0}", "{seed}", "{behavior}"):
            normalized = normalized.replace(alias, "{prompt}")
        return normalized
