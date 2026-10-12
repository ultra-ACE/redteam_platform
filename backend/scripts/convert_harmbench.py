"""把 HarmBench / AdvBench / TDC2023 数据集转换成系统可直接导入的 JSONL 文件。

转换后的字段对齐后端 BenchmarkImportService 的识别规则:
    external_id  -> test_cases.external_id
    prompt       -> test_cases.prompt
    raw_label    -> test_cases.source_label / 风险映射的原始标签
    language     -> test_cases.language
    metadata     -> test_cases.metadata

用法:
    python -m scripts.convert_harmbench
    python -m scripts.convert_harmbench --source "<HarmBench 根目录>" --output "<输出目录>"
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DEFAULT_SOURCE = Path(r"D:\StudyProgram\竞赛项目\准备工作\HarmBench\HarmBench-main")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "benchmark_datasets"

DATASETS = [
    {
        "relative_path": "data/behavior_datasets/harmbench_behaviors_text_all.csv",
        "output_name": "harmbench_text_all.jsonl",
        "source": "HarmBench",
        "category_field": "SemanticCategory",
        "extra_metadata": ["FunctionalCategory", "Tags", "ContextString"],
    },
    {
        "relative_path": "data/behavior_datasets/harmbench_behaviors_text_test.csv",
        "output_name": "harmbench_text_test.jsonl",
        "source": "HarmBench",
        "category_field": "SemanticCategory",
        "extra_metadata": ["FunctionalCategory", "Tags", "ContextString"],
    },
    {
        "relative_path": "data/behavior_datasets/harmbench_behaviors_text_val.csv",
        "output_name": "harmbench_text_val.jsonl",
        "source": "HarmBench",
        "category_field": "SemanticCategory",
        "extra_metadata": ["FunctionalCategory", "Tags", "ContextString"],
    },
    {
        "relative_path": "data/behavior_datasets/extra_behavior_datasets/advbench_behaviors.csv",
        "output_name": "advbench.jsonl",
        "source": "AdvBench",
        "category_field": "Category",
        "extra_metadata": ["Tags", "ContextString"],
    },
    {
        "relative_path": "data/behavior_datasets/extra_behavior_datasets/tdc2023_test_phase_behaviors.csv",
        "output_name": "tdc2023.jsonl",
        "source": "TDC2023",
        "category_field": "Category",
        "extra_metadata": ["Tags", "ContextString"],
    },
    {
        "relative_path": "data/behavior_datasets/extra_behavior_datasets/adv_training_behaviors.csv",
        "output_name": "adv_training.jsonl",
        "source": "AdvTraining",
        "category_field": "Category",
        "extra_metadata": ["Tags", "ContextString"],
    },
]


def convert_one(source_root: Path, spec: dict, output_dir: Path) -> dict:
    csv_path = source_root / spec["relative_path"]
    if not csv_path.exists():
        raise FileNotFoundError(f"未找到数据集文件: {csv_path}")

    output_path = output_dir / spec["output_name"]
    total = 0
    labelled = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file)
        with output_path.open("w", encoding="utf-8", newline="\n") as target_file:
            for index, row in enumerate(reader, start=1):
                behavior = (row.get("Behavior") or "").strip()
                if not behavior:
                    continue

                raw_label = (row.get(spec["category_field"]) or "").strip()
                if raw_label:
                    labelled += 1

                external_id = (row.get("BehaviorID") or "").strip() or f"{spec['output_name']}-{index}"

                metadata = {"source": spec["source"]}
                for key in spec["extra_metadata"]:
                    value = (row.get(key) or "").strip()
                    if value:
                        metadata[key.lower()] = value

                record = {
                    "external_id": external_id,
                    "prompt": behavior,
                    "raw_label": raw_label,
                    "language": "en",
                    "metadata": metadata,
                }
                target_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                total += 1

    return {
        "output": output_path,
        "total": total,
        "labelled": labelled,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="转换 HarmBench 系列数据集为可导入 JSONL")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="HarmBench 项目根目录")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出目录")
    args = parser.parse_args()

    source_root = Path(args.source)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"数据源: {source_root}")
    print(f"输出目录: {output_dir}")
    print("-" * 72)

    for spec in DATASETS:
        try:
            result = convert_one(source_root, spec, output_dir)
        except FileNotFoundError as exc:
            print(f"[跳过] {exc}")
            continue
        print(
            f"[完成] {result['output'].name:<32} "
            f"共 {result['total']:>4} 条, 其中带风险标签 {result['labelled']:>4} 条"
        )


if __name__ == "__main__":
    main()
