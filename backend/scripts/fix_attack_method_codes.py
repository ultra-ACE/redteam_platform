"""把历史攻击模板的 method_code 归一为契约里的四个固定值。

用法：
    cd backend
    .\\.venv\\Scripts\\python.exe scripts\\fix_attack_method_codes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许直接执行 python scripts/xxx.py 时找到 backend 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.models import AttackTemplate
from app.db.session import SessionLocal

ALIASES = {
    "role_play_api": "role_play",
    "roleplay": "role_play",
    "role-play": "role_play",
    "direct": "direct_request",
    "direct_api": "direct_request",
    "prefix": "prefix_injection",
    "prefix-injection": "prefix_injection",
    "refusal": "refusal_suppression",
    "refusal-suppression": "refusal_suppression",
}


def main() -> int:
    fixed = 0
    with SessionLocal() as session:
        for template in session.scalars(select(AttackTemplate)).all():
            current = (template.method_code or "").strip().lower()
            target = ALIASES.get(current)
            if target and target != current:
                template.method_code = target
                fixed += 1
        session.commit()
    print(f"fixed {fixed} attack template(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
