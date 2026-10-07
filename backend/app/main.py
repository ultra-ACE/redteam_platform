import json
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.request_context import reset_request_context, set_request_context
from app.services.audit import AuditLogService, resolve_audit_target, write_audit_log

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "大模型安全评测系统后端接口骨架。"
        "本服务默认监听本机，不包含登录、用户、角色权限和多租户。"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


def _resource_id_from_response(body: bytes | None, resource_type: str, fallback: int | None) -> int | None:
    if not body:
        return fallback
    try:
        data = json.loads(body).get("data")
        if not isinstance(data, dict):
            return fallback
        preferred = data.get(f"{resource_type}_id")
        if isinstance(preferred, int):
            return preferred
        for key, value in data.items():
            if key.endswith("_id") and isinstance(value, int):
                return value
    except (TypeError, ValueError):
        return fallback
    return fallback


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
    client_ip = request.client.host if request.client else None
    tokens = set_request_context(request_id, client_ip)
    try:
        response = await call_next(request)
        target = resolve_audit_target(request.method, request.url.path)

        response_body: bytes | None = None
        should_capture_body = (
            target is not None
            and response.status_code < 400
            and not target[0].endswith(".download")
            and response.headers.get("content-type", "").startswith("application/json")
        )
        if should_capture_body:
            chunks: list[bytes] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            response_body = b"".join(chunks)
            headers = dict(response.headers)
            headers.pop("content-length", None)
            response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
                background=getattr(response, "background", None),
            )

        response.headers["X-Request-ID"] = request_id

        if target is not None and response.status_code < 400:
            action, resource_type, resource_id = target
            resource_id = _resource_id_from_response(response_body, resource_type, resource_id)
            audit_kwargs = {
                "actor": request.headers.get("X-Operator") or "local",
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "before_data": None,
                "after_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
                "request_id": request_id,
                "ip": client_ip,
            }
            request_uow = getattr(request.state, "uow", None)
            try:
                if request_uow is not None and request_uow.session.is_active:
                    AuditLogService(request_uow).record(**audit_kwargs)
                else:
                    write_audit_log(**audit_kwargs)
            except Exception:
                logger.exception("Failed to write audit log for %s %s", request.method, request.url.path)

        return response
    finally:
        reset_request_context(tokens)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/api/v1", include_in_schema=False)
async def api_v1_root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
