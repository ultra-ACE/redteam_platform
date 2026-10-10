from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_root_compose_declares_full_stack() -> None:
    compose = _load_compose(PROJECT_ROOT / "docker-compose.yml")
    services = compose["services"]
    assert {"postgres", "redis", "migrate", "api", "worker", "frontend"}.issubset(services)
    assert services["api"]["build"]["context"] == "./backend"
    assert services["worker"]["build"]["context"] == "./backend"
    assert services["frontend"]["build"]["context"] == "./frontend"
    assert (PROJECT_ROOT / "backend" / "Dockerfile").exists()
    assert (PROJECT_ROOT / "frontend" / "Dockerfile").exists()
    assert (PROJECT_ROOT / "frontend" / "nginx.conf").exists()


def test_backend_compose_uses_relative_contexts() -> None:
    compose = _load_compose(PROJECT_ROOT / "backend" / "docker-compose.yml")
    services = compose["services"]
    assert services["api"]["build"]["context"] == "."
    assert services["worker"]["build"]["context"] == "."
    assert services["frontend"]["build"]["context"] == "../frontend"
