from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import (
    ApiResponse,
    HealthCheckData,
    Model,
    ModelCreateRequest,
    PaginatedData,
)
from app.services import ModelService, UnitOfWork

router = APIRouter(tags=["模型"])


@router.get(
    "/models",
    response_model=ApiResponse[PaginatedData[Model]],
    operation_id="listModels",
)
async def list_models(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    usage_scope: str | None = None,
    enabled: bool | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ModelService(uow)
    items = service.list_models(page=page, page_size=page_size, usage_scope=usage_scope, enabled=enabled)
    total = uow.models.count(usage_scope=usage_scope, enabled=enabled)
    return ok(PaginatedData[Model](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/models",
    response_model=ApiResponse[Model],
    operation_id="createModel",
)
async def create_model(
    payload: ModelCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ModelService(uow)
    model = service.create_model(payload)
    return ok(Model.model_validate(model).model_dump())


@router.post(
    "/models/{model_id}/health-check",
    response_model=ApiResponse[HealthCheckData],
    operation_id="checkModelHealth",
)
async def check_model_health(
    model_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ModelService(uow)
    status = await service.health_check(model_id)
    if status is None:
        raise HTTPException(status_code=404, detail="model not found")
    data = HealthCheckData(
        model_id=model_id,
        status=status.status,
        latency_ms=status.latency_ms,
        error_message=status.error_message,
    )
    return ok(data.model_dump())
