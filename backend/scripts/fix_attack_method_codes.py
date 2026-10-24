"""把历史攻击模板中已删除的基线分类统一归一为 custom。

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

def main() -> int:
    fixed = 0
    with SessionLocal() as session:
        for template in session.scalars(select(AttackTemplate)).all():
            current = (template.method_code or "").strip().lower()
            if current != "custom":
                template.method_code = "custom"
                fixed += 1
        session.commit()
    print(f"fixed {fixed} attack template(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
