"""中文数据集适配器。

识别中文列名，例如::

    编号, 提示词, 风险类型, 语言
    用例ID, 问题, 类别

这类数据集通常自带中文风险标签（如"生化武器"、"虚假信息"），需要靠别名词典
归一到统一风险分类。
"""
from typing import Any

from app.services.dataset_adapters.base import (
    CanonicalCase,
    DatasetAdapter,
    RowIndex,
    normalize_key,
    split_labels,
)

PROMPT_FIELDS = ("提示词", "问题", "内容", "指令", "输入", "文本", "query", "prompt")
ID_FIELDS = ("编号", "用例编号", "用例id", "样本编号", "external_id", "id")
LABEL_FIELDS = ("风险类型", "风险类别", "标签", "类别", "风险等级", "raw_label", "label", "category")
CODE_FIELDS = ("统一风险编码", "风险编码", "normalized_risk_codes", "risk_category_code")
SYSTEM_FIELDS = ("系统提示词", "系统提示", "system_prompt")
LANGUAGE_FIELDS = ("语言", "language", "lang")

#: 只有出现真正的中文列名才认为命中本适配器，避免把英文通用数据集误判为中文集
CHINESE_SIGNATURE = (
    "提示词", "问题", "内容", "指令", "输入", "文本",
    "编号", "用例编号", "样本编号",
    "风险类型", "风险类别", "标签", "类别", "风险等级",
    "语言", "系统提示词", "系统提示", "统一风险编码", "风险编码",
)


class ChineseGenericAdapter(DatasetAdapter):
    name = "chinese_generic"
    display_name = "中文通用数据集"
    description = "识别 提示词/问题/内容 与 风险类型/标签/类别 等中文列名。"
    field_candidates = {
        "prompt": PROMPT_FIELDS,
        "external_id": ID_FIELDS,
        "raw_label": LABEL_FIELDS,
        "normalized_risk_codes": CODE_FIELDS,
        "system_prompt": SYSTEM_FIELDS,
        "language": LANGUAGE_FIELDS,
    }

    def score(self, headers: set[str], file_name: str = "") -> float:
        hits = sum(1 for name in CHINESE_SIGNATURE if normalize_key(name) in headers)
        if hits == 0:
            return 0.0
        # 命中越多越可信，但不超过通用适配器的前提下要能压过它
        return min(0.5 + 0.15 * hits, 0.95)

    def normalize(
        self,
        row: dict[str, Any],
        row_number: int,
        file_name: str = "",
    ) -> CanonicalCase:
        view = RowIndex(row)
        prompt = view.get(*PROMPT_FIELDS)
        if not prompt:
            raise ValueError("missing prompt (未找到 提示词/问题/内容 字段)")

        return CanonicalCase(
            external_id=str(view.get(*ID_FIELDS) or f"case-{row_number}"),
            prompt=str(prompt),
            system_prompt=str(view.get(*SYSTEM_FIELDS)) if view.get(*SYSTEM_FIELDS) else None,
            language=str(view.get(*LANGUAGE_FIELDS) or "zh"),
            raw_labels=split_labels(view.get(*LABEL_FIELDS)),
            risk_codes=split_labels(view.get(*CODE_FIELDS)),
            metadata=view.leftover(
                PROMPT_FIELDS + ID_FIELDS + LABEL_FIELDS + CODE_FIELDS + SYSTEM_FIELDS + LANGUAGE_FIELDS
            ),
        )
