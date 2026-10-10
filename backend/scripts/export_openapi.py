"""Export the FastAPI runtime OpenAPI document to the repository root."""

import sys
from pathlib import Path

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    output = PROJECT_ROOT / "openapi.yaml"
    schema = app.openapi()
    content = (
        "# Generated from the FastAPI runtime OpenAPI schema.\n"
        "# Refresh: cd backend && .venv\\Scripts\\python.exe scripts\\export_openapi.py\n\n"
    )
    content += yaml.safe_dump(
        schema,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    output.write_text(content, encoding="utf-8")
    print(f"exported {len(schema.get('paths', {}))} paths to {output}")


if __name__ == "__main__":
    main()
