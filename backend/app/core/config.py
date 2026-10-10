import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "大模型安全评测系统 API"
    version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    local_token: str | None = None
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "sqlite:///./data/app.db",
        )
    )
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "./data"))
    celery_broker_url: str = field(
        default_factory=lambda: os.getenv(
            "CELERY_BROKER_URL",
            "redis://127.0.0.1:6379/0",
        )
    )
    celery_result_backend: str = field(
        default_factory=lambda: os.getenv(
            "CELERY_RESULT_BACKEND",
            "redis://127.0.0.1:6379/1",
        )
    )
    celery_task_always_eager: bool = field(
        default_factory=lambda: _env_bool("CELERY_TASK_ALWAYS_EAGER", False)
    )
    celery_task_eager_propagates: bool = field(
        default_factory=lambda: _env_bool("CELERY_TASK_EAGER_PROPAGATES", True)
    )
    default_model_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("DEFAULT_MODEL_TIMEOUT_SECONDS", "120"))
    )
    max_upload_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
    )


settings = Settings()
