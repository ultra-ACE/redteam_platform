"""修复“外部编号等于提示词”的测试用例编号。

背景：TDC2023 数据集自带的 ``BehaviorID`` 列写的不是编号，而是把整段 Behavior
文本复制了一遍。早期导入脚本直接拿它当 ``external_id``，于是那 50 条用例的
编号变成了一整句话，界面上就成了"ID 显示的是提示词"。

修复方式：把编号改成 ``{版本名}-{序号}``，原始值转存到
``metadata.original_behavior_id``。只处理 ``external_id`` 与 ``prompt`` 完全相同的
记录，其它用例不受影响。

用法::

    cd backend
    .venv\\Scripts\\python.exe -m scripts.fix_external_ids            # 只预览
    .venv\\Scripts\\python.exe -m scripts.fix_external_ids --apply    # 真正修改
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkVersion, TestCase  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def _prefix(version: str | None, version_id: int) -> str:
    slug = re.sub(r"[^0-9a-zA-Z._-]+", "-", (version or "").strip().lower()).strip("-")
    return slug or f"version{version_id}"


def main() -> None:
    parser = argparse.ArgumentParser(description="修复与提示词重复的用例外部编号")
    parser.add_argument("--apply", action="store_true", help="真正执行修改；不加则只预览")
    args = parser.parse_args()

    with SessionLocal() as session:
        broken = session.scalars(
            select(TestCase)
            .where(TestCase.external_id == TestCase.prompt)
            .order_by(TestCase.benchmark_version_id, TestCase.id)
        ).all()

        if not broken:
            print("没有发现编号与提示词完全相同的用例。")
            return

        version_cache: dict[int, BenchmarkVersion | None] = {}
        counters: dict[int, int] = {}
        planned: list[tuple[TestCase, str]] = []
        for case in broken:
            version_id = case.benchmark_version_id
            if version_id not in version_cache:
                version_cache[version_id] = session.get(BenchmarkVersion, version_id)
            version = version_cache[version_id]
            prefix = _prefix(version.version if version else None, version_id)
            counters[version_id] = counters.get(version_id, 0) + 1
            planned.append((case, f"{prefix}-{counters[version_id]}"))

        print(f"待修复用例：{len(planned)} 条，涉及 {len(counters)} 个版本")
        for case, new_id in planned[:5]:
            print(f"  #{case.id}  {case.external_id[:44]!r}")
            print(f"        -> {new_id}")
        if len(planned) > 5:
            print(f"  ... 其余 {len(planned) - 5} 条同理")

        if not args.apply:
            print()
            print("以上为预览。加 --apply 才会真正修改编号。")
            return

        for case, new_id in planned:
            metadata = dict(case.case_metadata or {})
            metadata.setdefault("original_behavior_id", case.external_id)
            case.case_metadata = metadata
            case.external_id = new_id[:128]
        session.commit()
        print()
        print(f"已修复 {len(planned)} 条用例编号，原始值保存在 metadata.original_behavior_id。")


if __name__ == "__main__":
    main()
