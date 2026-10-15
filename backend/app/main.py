from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="大模型越狱攻击安全评测系统后端接口。",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/api/v1", include_in_schema=False)
async def api_v1_root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
