from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)


def set_request_context(
    request_id: str,
    client_ip: str | None = None,
) -> tuple[Token, Token]:
    return _request_id.set(request_id), _client_ip.set(client_ip)


def reset_request_context(tokens: tuple[Token, Token]) -> None:
    request_id_token, client_ip_token = tokens
    _request_id.reset(request_id_token)
    _client_ip.reset(client_ip_token)


def get_context_request_id() -> str | None:
    return _request_id.get()


def get_context_client_ip() -> str | None:
    return _client_ip.get()
