from uuid import uuid4
from typing import Any

from app.core.request_context import get_context_request_id

from fastapi import Header, Security
from fastapi.security import APIKeyHeader


def get_request_id() -> str:
    return get_context_request_id() or f"req_{uuid4().hex}"


def get_operator(x_operator: str = Header(default="local", alias="X-Operator")) -> str:
    return x_operator


local_token_header = APIKeyHeader(name="X-Local-Token", scheme_name="LocalToken", auto_error=False)


def require_local_token(token: str | None = Security(local_token_header)) -> None:
    """Local token placeholder.

    Skeleton stage: always pass. Replace with configuration-based validation later.
    """
    return None


def ok(data: Any) -> dict[str, Any]:
    return {
        "code": "OK",
        "message": "success",
        "data": data,
        "request_id": get_request_id(),
    }

