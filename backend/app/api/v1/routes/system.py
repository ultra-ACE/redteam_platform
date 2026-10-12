import redis as redis_lib
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.core.config import settings
from app.db.session import engine
from app.schemas import (
    ApiResponse,
    AuditLog,
    HealthData,
    PaginatedData,
    SystemConfig,
    SystemConfigUpdate,
)
from app.services import SystemService, UnitOfWork

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=ApiResponse[HealthData], operation_id="getHealth")
async def get_health(response: Response) -> dict:
    """真实探测数据库和 Redis，避免依赖服务掉线却仍显示健康。"""
    database_status = "up"
    redis_status = "up"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "down"

    try:
        client = redis_lib.Redis.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
    except Exception:
        redis_status = "down"

    overall = "healthy" if database_status == "up" and redis_status == "up" else "degraded"
    if overall != "healthy":
        response.status_code = 503

    data = HealthData(
        status=overall,
        database=database_status,
        redis=redis_status,
        storage="up",
        version=settings.version,
    )
    return ok(data.model_dump())


@router.get(
    "/system-configs",
    response_model=ApiResponse[PaginatedData[SystemConfig]],
    operation_id="listSystemConfigs",
)
async def list_system_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = SystemService(uow)
    items = service.list_configs(page=page, page_size=page_size)
    total = uow.system_configs.count()
    return ok(PaginatedData[SystemConfig](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.patch(
    "/system-configs/{config_key}",
    response_model=ApiResponse[SystemConfig],
    operation_id="updateSystemConfig",
)
async def update_system_config(
    config_key: str,
    payload: SystemConfigUpdate,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = SystemService(uow)
    config = service.update_config(config_key, payload.config_value)
    return ok(SystemConfig.model_validate(config).model_dump())


@router.get(
    "/audit-logs",
    response_model=ApiResponse[PaginatedData[AuditLog]],
    operation_id="listAuditLogs",
)
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = SystemService(uow)
    items = service.list_audit_logs(page=page, page_size=page_size)
    total = uow.audit_logs.count()
    return ok(PaginatedData[AuditLog](items=items, page=page, page_size=page_size, total=total).model_dump())
