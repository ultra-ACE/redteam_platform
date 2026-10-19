"""把 JSONL 模板批量导入 attack_templates。

用法：
    cd backend
    .\\.venv\\Scripts\\python.exe scripts\\import_attack_templates.py human_jailbreaks.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import AttackTemplate
from app.db.session import SessionLocal
from app.services.attack_templates import AttackTemplateService
from app.services.uow import UnitOfWork


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/import_attack_templates.py <templates.jsonl>")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"file not found: {path}")
        return 2

    created = 0
    skipped = 0
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            method_code = record.get("method_code", "role_play")
            name = record["name"]
            version = record.get("version", "v1")
            existing = uow.attack_templates.list(
                page=1,
                page_size=1,
                method_code=method_code,
                name=name,
                version=version,
            )
            if existing:
                skipped += 1
                continue
            template_text = AttackTemplateService._normalize_template_text(
                record["template_text"]
            )
            uow.attack_templates.add(
                AttackTemplate(
                    method_code=method_code,
                    name=name,
                    template_text=template_text,
                    variables=record.get("variables") or [],
                    version=version,
                    status="active",
                )
            )
            created += 1
        uow.commit()

    print(f"created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
