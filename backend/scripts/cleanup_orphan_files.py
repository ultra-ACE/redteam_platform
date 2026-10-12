"""清理 files 表中的孤儿记录。

背景：报告生成任务曾被重复投递，同一份报告被生成几十次。每次生成都会
覆盖同一个磁盘路径并插入一条新的 files 记录，于是台账里堆积了大量记录，
它们指向的文件早已被后续生成覆盖，只剩下 reports.file_id 指向的那一条有效。

安全约定：
    本脚本**只删除数据库记录，不删除磁盘文件**。因为孤儿记录与有效记录
    可能指向同一个路径，误删磁盘文件会直接破坏正在使用的报告。

用法::

    cd backend
    .venv\\Scripts\\python.exe -m scripts.cleanup_orphan_files            # 只预览
    .venv\\Scripts\\python.exe -m scripts.cleanup_orphan_files --apply    # 真正删除
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkVersion, Report, StoredFile, TaskAttempt  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

#: 由系统生成、必须被某个业务对象引用的文件归属
SYSTEM_OWNERS = ("report", "benchmark_import", "model_response")


def _referenced_file_ids(session) -> set[int]:
    ids: set[int] = set()
    for column in (
        Report.file_id,
        BenchmarkVersion.source_file_id,
        TaskAttempt.output_file_id,
    ):
        rows = session.scalars(select(column).where(column.is_not(None))).all()
        ids.update(int(value) for value in rows if value is not None)
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 files 表中的孤儿记录（只删记录，不删文件）")
    parser.add_argument("--apply", action="store_true", help="真正执行删除；不加此参数只预览")
    args = parser.parse_args()

    with SessionLocal() as session:
        referenced = _referenced_file_ids(session)
        candidates = session.scalars(
            select(StoredFile).where(StoredFile.owner_type.in_(SYSTEM_OWNERS))
        ).all()
        orphans = [item for item in candidates if item.id not in referenced]

        all_files = session.scalars(select(StoredFile.id)).all()

        print(f"files 表总记录数 : {len(all_files)}")
        print(f"被业务对象引用   : {len(referenced)}")
        print(f"待清理孤儿记录   : {len(orphans)}")

        by_owner: dict[str, int] = {}
        for item in orphans:
            by_owner[item.owner_type or "(空)"] = by_owner.get(item.owner_type or "(空)", 0) + 1
        for owner, count in sorted(by_owner.items(), key=lambda pair: -pair[1]):
            print(f"  - {owner:<20} {count} 条")

        if not orphans:
            print("没有需要清理的孤儿记录。")
            return

        if not args.apply:
            print()
            print("以上为预览。加 --apply 才会真正删除这些数据库记录。")
            print("磁盘文件不会被删除。")
            return

        for item in orphans:
            session.delete(item)
        session.commit()
        print()
        print(f"已删除 {len(orphans)} 条孤儿记录，磁盘文件保持不动。")

        remaining = session.scalars(
            select(StoredFile).where(StoredFile.owner_type.in_(SYSTEM_OWNERS))
        ).all()
        missing = []
        skipped = 0
        for item in remaining:
            path = item.stored_path
            if not path:
                continue
            # 数据库里存的是容器内路径（/app/data/...），在宿主上直接检查会误报
            if path.startswith("/app/") and sys.platform.startswith("win"):
                skipped += 1
                continue
            if not Path(path).exists():
                missing.append(item)
        if missing:
            print(f"提醒：仍有 {len(missing)} 条记录指向的磁盘文件不存在，请人工确认。")
        elif skipped:
            print(f"说明：{skipped} 条记录存放的是容器内路径，已跳过宿主侧存在性检查。")
            print("      如需核对，请进容器执行：docker exec backend-api-1 test -f <stored_path>")


if __name__ == "__main__":
    main()
