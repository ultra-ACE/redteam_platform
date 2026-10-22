"""中文数据集适配器（含 JailBench 中文子集）。

识别中文列名，例如::

    编号, 提示词, 数据集类型, 样本类型, 原始标签, 语言
    用例ID, 问题, 类型, 样本种类, 标签

契约冻结后 ``dataset_type`` 只允许 ``benign`` / ``harmful`` / ``jailbreak``，
``sample_kind`` 只允许 ``seed`` / ``template``。适配器负责把中文取值翻译为
规范枚举；原始标签字段 ``原始标签`` 仅作为元数据保留，不再映射风险类别。
"""
from typing import Any

from app.services.dataset_adapters.base import (
    CanonicalCase,
    DatasetAdapter,
    RowIndex,
    content_external_id,
    normalize_key,
    split_labels,
)

PROMPT_FIELDS = ("提示词", "问题", "内容", "指令", "输入", "文本", "query", "prompt")
ID_FIELDS = ("编号", "用例编号", "用例id", "样本编号", "external_id", "id")
LABEL_FIELDS = (
    "原始标签", "风险类型", "风险类别", "标签", "类别", "风险等级",
    "raw_label", "label", "category",
)
CODE_FIELDS = ("统一风险编码", "风险编码", "normalized_risk_codes", "risk_category_code")
SYSTEM_FIELDS = ("系统提示词", "系统提示", "system_prompt")
LANGUAGE_FIELDS = ("语言", "language", "lang")
#: 契约冻结新增字段
DATASET_TYPE_FIELDS = ("数据集类型", "数据类型", "样本类别", "dataset_type", "datasettype")
SAMPLE_KIND_FIELDS = ("样本类型", "样本种类", "样本形态", "sample_kind", "samplekind")

#: 只有出现真正的中文列名才认为命中本适配器，避免把英文通用数据集误判为中文集
CHINESE_SIGNATURE = (
    "提示词", "问题", "内容", "指令", "输入", "文本",
    "编号", "用例编号", "样本编号",
    "风险类型", "风险类别", "标签", "类别", "风险等级",
    "语言", "系统提示词", "系统提示",
    "数据集类型", "数据类型", "样本类型", "样本种类",
    "原始标签",
)


class ChineseGenericAdapter(DatasetAdapter):
    name = "chinese_generic"
    display_name = "中文通用数据集（含 JailBench 中文子集）"
    description = "识别 提示词/问题/内容、数据集类型、样本类型、原始标签、语言 等中文列名。"
    field_candidates = {
        "prompt": PROMPT_FIELDS,
        "external_id": ID_FIELDS,
        "raw_label": LABEL_FIELDS,
        "normalized_risk_codes": CODE_FIELDS,
        "system_prompt": SYSTEM_FIELDS,
        "language": LANGUAGE_FIELDS,
        "dataset_type": DATASET_TYPE_FIELDS,
        "sample_kind": SAMPLE_KIND_FIELDS,
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

        # 契约冻结：dataset_type 默认 harmful，sample_kind 无值时为 None；
        # CanonicalCase.__post_init__ 会再做一次规范化兜底。
        dataset_type = view.get(*DATASET_TYPE_FIELDS) or "harmful"
        sample_kind = view.get(*SAMPLE_KIND_FIELDS)
        system_prompt = str(view.get(*SYSTEM_FIELDS)) if view.get(*SYSTEM_FIELDS) else None

        consumed = (
            PROMPT_FIELDS + ID_FIELDS + LABEL_FIELDS + CODE_FIELDS
            + SYSTEM_FIELDS + LANGUAGE_FIELDS
            + DATASET_TYPE_FIELDS + SAMPLE_KIND_FIELDS
        )

        return CanonicalCase(
            external_id=str(
                view.get(*ID_FIELDS)
                or content_external_id(prompt, system_prompt)
            ),
            prompt=str(prompt),
            system_prompt=system_prompt,
            language=str(view.get(*LANGUAGE_FIELDS) or "zh"),
            dataset_type=str(dataset_type),
            sample_kind=str(sample_kind) if sample_kind is not None else None,
            raw_labels=split_labels(view.get(*LABEL_FIELDS)),
            risk_codes=split_labels(view.get(*CODE_FIELDS)),
            metadata=view.leftover(consumed),
        )
