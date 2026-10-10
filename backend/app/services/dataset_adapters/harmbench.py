"""HarmBench 行为数据集适配器。

原始 CSV 表头::

    Behavior, FunctionalCategory, SemanticCategory, Tags, ContextString, BehaviorID

其中 ``SemanticCategory`` 是 HarmBench 的风险标签（如 ``chemical_biological``），
``BehaviorID`` 是可读的用例编号（如 ``safrole_oil_extraction_guide``）。
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

BEHAVIOR = "Behavior"
BEHAVIOR_ID = "BehaviorID"
SEMANTIC_CATEGORY = "SemanticCategory"
FUNCTIONAL_CATEGORY = "FunctionalCategory"
TAGS = "Tags"
CONTEXT_STRING = "ContextString"


class HarmBenchAdapter(DatasetAdapter):
    name = "harmbench_csv"
    display_name = "HarmBench 行为数据集"
    description = "识别 Behavior / BehaviorID / SemanticCategory 结构，标签来自 SemanticCategory。"
    field_candidates = {
        "prompt": (BEHAVIOR,),
        "external_id": (BEHAVIOR_ID,),
        "raw_label": (SEMANTIC_CATEGORY,),
        "metadata.functional_category": (FUNCTIONAL_CATEGORY,),
        "metadata.tags": (TAGS,),
        "metadata.context_string": (CONTEXT_STRING,),
    }

    def score(self, headers: set[str], file_name: str = "") -> float:
        if normalize_key(BEHAVIOR) not in headers:
            return 0.0
        score = 0.6
        if normalize_key(SEMANTIC_CATEGORY) in headers:
            score += 0.4
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
            raise ValueError("missing prompt (HarmBench 的 Behavior 字段为空)")

        metadata: dict[str, Any] = {"source": "HarmBench"}
        for source in (FUNCTIONAL_CATEGORY, TAGS, CONTEXT_STRING):
            value = view.get(source)
            if value is not None:
                metadata[source] = value
        external_id, replaced = safe_external_id(
            view.get(BEHAVIOR_ID),
            fallback=f"harmbench-{row_number}",
            prompt=prompt,
        )
        if replaced is not None:
            metadata["original_behavior_id"] = replaced

        return CanonicalCase(
            external_id=external_id,
            prompt=str(prompt),
            system_prompt=None,
            language="en",
            raw_labels=split_labels(view.get(SEMANTIC_CATEGORY)),
            risk_codes=[],
            metadata=metadata,
        )
