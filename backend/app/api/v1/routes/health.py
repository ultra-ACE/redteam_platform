import redis as redis_lib
from fastapi import APIRouter, Response
from sqlalchemy import text

from app.api.utils import ok
from app.core.config import settings
from app.db.session import engine
from app.schemas import ApiResponse, HealthData

router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=ApiResponse[HealthData], operation_id="getHealth")
async def get_health(response: Response) -> dict:
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
