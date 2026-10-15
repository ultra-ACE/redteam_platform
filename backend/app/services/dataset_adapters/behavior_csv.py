"""AdvBench / TDC2023 风格的 ``Behavior`` CSV 适配器。

原始 CSV 表头::

    Behavior, Category, Tags, ContextString, BehaviorID

与 HarmBench 的区别是没有 ``SemanticCategory``。这两个数据集的 ``Category``
列在实际发行版本中经常是空的，此时用例会被记为"无风险标签"，进入导入报告的
未标注列表，而不是被胡乱归到一个类别。
"""
from typing import Any

from app.services.dataset_adapters.base import (
    CanonicalCase,
    DatasetAdapter,
    RowIndex,
    normalize_key,
    safe_external_id,
    split_labels,
)
from app.services.dataset_adapters.harmbench import (
    BEHAVIOR,
    BEHAVIOR_ID,
    CONTEXT_STRING,
    SEMANTIC_CATEGORY,
    TAGS,
)

CATEGORY = "Category"


class BehaviorCsvAdapter(DatasetAdapter):
    name = "behavior_csv"
    display_name = "Behavior 型行为数据集（AdvBench / TDC2023）"
    description = "识别 Behavior / Category / BehaviorID 结构，标签来自 Category。"
    field_candidates = {
        "prompt": (BEHAVIOR,),
        "external_id": (BEHAVIOR_ID,),
        "raw_label": (CATEGORY,),
        "metadata.tags": (TAGS,),
        "metadata.context_string": (CONTEXT_STRING,),
    }

    def score(self, headers: set[str], file_name: str = "") -> float:
        if normalize_key(BEHAVIOR) not in headers:
            return 0.0
        if normalize_key(SEMANTIC_CATEGORY) in headers:
            # 有 SemanticCategory 说明是 HarmBench，交给 HarmBench 适配器
            return 0.0
        score = 0.6
        if normalize_key(CATEGORY) in headers:
            score += 0.2
        if normalize_key(BEHAVIOR_ID) in headers:
            score += 0.1
        return min(score, 1.0)

    def normalize(
        self,
        row: dict[str, Any],
        row_number: int,
        file_name: str = "",
    ) -> CanonicalCase:
        view = RowIndex(row)
        prompt = view.get(BEHAVIOR)
        if not prompt:
            raise ValueError("missing prompt (Behavior 字段为空)")

        lowered = file_name.lower()
        if "tdc" in lowered:
            source_name = "TDC2023"
        elif "advbench" in lowered:
            source_name = "AdvBench"
        else:
            source_name = "BehaviorCSV"
        external_id, replaced = safe_external_id(
            view.get(BEHAVIOR_ID),
            fallback=f"{source_name.lower()}-{row_number}",
            prompt=prompt,
        )

        metadata: dict[str, Any] = {"source": source_name}
        for source in (CATEGORY, TAGS, CONTEXT_STRING):
            value = view.get(source)
            if value is not None:
                metadata[source] = value
        if replaced is not None:
            metadata["original_behavior_id"] = replaced

        return CanonicalCase(
            external_id=external_id,
            prompt=str(prompt),
            system_prompt=None,
            language="en",
            raw_labels=split_labels(view.get(CATEGORY)),
            risk_codes=[],
            metadata=metadata,
        )
