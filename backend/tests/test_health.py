from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    # 200 表示全部依赖可用；503 表示数据库或 Redis 掉线，此时 status 为 degraded
    assert response.status_code in (200, 503)
    payload = response.json()
    assert payload["code"] == "OK"
    assert payload["data"]["database"] == "up"
    assert payload["data"]["status"] in {"healthy", "degraded"}
