"""任务 SSE 事件流契约测试。"""
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_task_events_404_task_error() -> None:
    """不存在的任务应收到 task_error 事件并结束流。"""
    with client.stream("GET", "/api/v1/evaluation-tasks/999999/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        first_line = None
        for line in response.iter_lines():
            if line:
                first_line = line
                break
    assert first_line is not None
    assert first_line.startswith("event: task_error") or first_line.startswith("data:")