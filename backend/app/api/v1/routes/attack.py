from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import (
    ApiResponse,
    AttackMethod,
    AttackMethodCreateRequest,
    AttackMethodUpdateRequest,
    AttackTemplate,
    AttackTemplateCreateRequest,
    AttackTemplatePreviewRequest,
    AttackTemplatePreviewResult,
    AttackTemplateUpdateRequest,
    AttackTemplateValidationResult,
    AttackTemplateVersionCreateRequest,
    PaginatedData,
)
from app.services import AttackTemplateService, UnitOfWork

router = APIRouter()


@router.get(
    "/attack-methods",
    response_model=ApiResponse[PaginatedData[AttackMethod]],
    operation_id="listAttackMethods",
    tags=["攻击方法"],
)
async def list_attack_methods(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    enabled: bool | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = AttackTemplateService(uow)
    items = service.list_methods(page=page, page_size=page_size, enabled=enabled)
    total = uow.attack_methods.count(enabled=enabled)
    return ok(PaginatedData[AttackMethod](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/attack-methods",
    response_model=ApiResponse[AttackMethod],
    operation_id="createAttackMethod",
    tags=["攻击方法"],
)
async def create_attack_method(
    payload: AttackMethodCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    method = AttackTemplateService(uow).create_method(payload)
    return ok(AttackMethod.model_validate(method).model_dump())


@router.patch(
    "/attack-methods/{method_id}",
    response_model=ApiResponse[AttackMethod],
    operation_id="updateAttackMethod",
    tags=["攻击方法"],
)
async def update_attack_method(
    method_id: int,
    payload: AttackMethodUpdateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    method = AttackTemplateService(uow).update_method(method_id, payload)
    if method is None:
        raise HTTPException(status_code=404, detail="attack method not found")
    return ok(AttackMethod.model_validate(method).model_dump())


@router.delete(
    "/attack-methods/{method_id}",
    response_model=ApiResponse[AttackMethod],
    operation_id="disableAttackMethod",
    tags=["攻击方法"],
)
async def disable_attack_method(
    method_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    method = AttackTemplateService(uow).disable_method(method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="attack method not found")
    return ok(AttackMethod.model_validate(method).model_dump())


@router.get(
    "/attack-templates",
    response_model=ApiResponse[PaginatedData[AttackTemplate]],
    operation_id="listAttackTemplates",
    tags=["攻击模板"],
)
async def list_attack_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    attack_method_id: int | None = None,
    name: str | None = None,
    status: str | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = AttackTemplateService(uow)
    items = service.list_templates(
        page=page,
        page_size=page_size,
        attack_method_id=attack_method_id,
        name=name,
        status=status,
    )
    total = uow.attack_templates.count(attack_method_id=attack_method_id, status=status)
    return ok(PaginatedData[AttackTemplate](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/attack-templates",
    response_model=ApiResponse[AttackTemplate],
    operation_id="createAttackTemplate",
    tags=["攻击模板"],
)
async def create_attack_template(
    payload: AttackTemplateCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    try:
        template = AttackTemplateService(uow).create_template(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(AttackTemplate.model_validate(template).model_dump())


@router.get(
    "/attack-templates/{template_id}",
    response_model=ApiResponse[AttackTemplate],
    operation_id="getAttackTemplate",
    tags=["攻击模板"],
)
async def get_attack_template(
    template_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    template = AttackTemplateService(uow).get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    return ok(AttackTemplate.model_validate(template).model_dump())


@router.patch(
    "/attack-templates/{template_id}",
    response_model=ApiResponse[AttackTemplate],
    operation_id="updateAttackTemplate",
    tags=["攻击模板"],
)
async def update_attack_template(
    template_id: int,
    payload: AttackTemplateUpdateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    try:
        template = AttackTemplateService(uow).update_template(template_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if template is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    return ok(AttackTemplate.model_validate(template).model_dump())


@router.delete(
    "/attack-templates/{template_id}",
    response_model=ApiResponse[AttackTemplate],
    operation_id="disableAttackTemplate",
    tags=["攻击模板"],
)
async def disable_attack_template(
    template_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    template = AttackTemplateService(uow).disable_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    return ok(AttackTemplate.model_validate(template).model_dump())


@router.post(
    "/attack-templates/{template_id}/validate",
    response_model=ApiResponse[AttackTemplateValidationResult],
    operation_id="validateAttackTemplate",
    tags=["攻击模板"],
)
async def validate_attack_template(
    template_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = AttackTemplateService(uow)
    template = service.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    result = service.validate_template(template.template_text, template.variables or [])
    return ok(result.model_dump())


@router.post(
    "/attack-templates/{template_id}/preview",
    response_model=ApiResponse[AttackTemplatePreviewResult],
    operation_id="previewAttackTemplate",
    tags=["攻击模板"],
)
async def preview_attack_template(
    template_id: int,
    payload: AttackTemplatePreviewRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    result = AttackTemplateService(uow).preview_template(template_id, payload.variables)
    if result is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    return ok(result.model_dump())


@router.get(
    "/attack-templates/{template_id}/versions",
    response_model=ApiResponse[list[AttackTemplate]],
    operation_id="listAttackTemplateVersions",
    tags=["攻击模板"],
)
async def list_attack_template_versions(
    template_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    items = AttackTemplateService(uow).list_versions(template_id)
    return ok([AttackTemplate.model_validate(item).model_dump() for item in items])


@router.post(
    "/attack-templates/{template_id}/versions",
    response_model=ApiResponse[AttackTemplate],
    operation_id="createAttackTemplateVersion",
    tags=["攻击模板"],
)
async def create_attack_template_version(
    template_id: int,
    payload: AttackTemplateVersionCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    try:
        version = AttackTemplateService(uow).create_version(template_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if version is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    return ok(AttackTemplate.model_validate(version).model_dump())


@router.post(
    "/attack-templates/{template_id}/publish",
    response_model=ApiResponse[AttackTemplate],
    operation_id="publishAttackTemplateVersion",
    tags=["攻击模板"],
)
async def publish_attack_template_version(
    template_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    template = AttackTemplateService(uow).publish_version(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="attack template not found")
    return ok(AttackTemplate.model_validate(template).model_dump())
