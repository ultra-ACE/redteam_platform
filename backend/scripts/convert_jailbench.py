"""把 JailBench.csv 转成系统中文适配器可直接导入的 CSV。

原始列: query, 一级领域, 二级领域
目标列: external_id, 提示词, 数据集类型, 样本类型, 原始标签, 语言
"""
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT_ROOT / "benchmark_datasets" / "zh_jailbench_raw.csv"
TARGET = PROJECT_ROOT / "benchmark_datasets" / "zh_jailbench.csv"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"未找到源文件: {SOURCE}，请先下载 JailBench.csv")

    total = 0
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as src, \
         TARGET.open("w", encoding="utf-8", newline="") as dst:

        reader = csv.DictReader(src)
        writer = csv.DictWriter(
            dst,
            fieldnames=["external_id", "提示词", "数据集类型", "样本类型", "原始标签", "语言"],
        )
        writer.writeheader()

        for index, row in enumerate(reader, start=1):
            prompt = (row.get("query") or "").strip()
            if not prompt:
                continue

            primary = (row.get("一级领域") or "").strip()
            secondary = (row.get("二级领域") or "").strip()
            label = f"{primary}/{secondary}" if secondary else primary

            writer.writerow({
                "external_id": f"jailbench-{index:05d}",
                "提示词": prompt,
                "数据集类型": "harmful",
                "样本类型": "seed",
                "原始标签": label,
                "语言": "zh",
            })
            total += 1

    print(f"转换完成: {total} 条 -> {TARGET}")


if __name__ == "__main__":
    main()