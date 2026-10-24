"""把 HarmBench 的人工越狱模板转换成可导入的 JSONL。

用法：
    cd backend
    .\\.venv\\Scripts\\python.exe scripts\\convert_human_jailbreaks.py ^
        "F:\\...\\HarmBench-main\\baselines\\human_jailbreaks\\jailbreaks.py" ^
        human_jailbreaks.jsonl
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

DEFAULT_INPUT = Path(
    r"F:\StudyProgram\竞赛项目\准备工作\HarmBench\HarmBench-main"
    r"\baselines\human_jailbreaks\jailbreaks.py"
)


def load_jailbreaks(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "JAILBREAKS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, list):
                return [str(item) for item in value]
    raise ValueError(f"JAILBREAKS not found in {path}")


def normalize(text: str) -> str:
    # 源文件里部分 emoji 以孤立代理字符保存，写 UTF-8 前需要剔除
    text = "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)
    normalized = text.replace("{0}", "{prompt}").replace("{seed}", "{prompt}")
    if "{prompt}" not in normalized:
        normalized = f"{normalized.rstrip()}\n\n{{prompt}}"
    return normalized


def main() -> int:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("human_jailbreaks.jsonl")

    templates = load_jailbreaks(input_path)
    with output_path.open("w", encoding="utf-8") as handle:
        for index, item in enumerate(templates, start=1):
            record = {
                "name": f"Human Jailbreak {index:03d}",
                "method_code": "custom",
                "template_text": normalize(item),
                "variables": ["prompt"],
                "version": "v1",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"converted {len(templates)} templates -> {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
