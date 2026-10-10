"""通用适配器：识别 prompt / question / input / text 等常见字段名。

这是兜底适配器，任何数据集都能落到它上面；缺少 prompt 的行会按行报错，
行为与系统最初的导入实现保持一致。
"""
from typing import Any

from app.services.dataset_adapters.base import (
    CanonicalCase,
    DatasetAdapter,
    RowIndex,
    split_labels,
)


class GenericAdapter(DatasetAdapter):
    name = "generic"
    display_name = "通用数据集"
    description = "识别 prompt、question、input、text、query、instruction 等通用字段名。"
    field_candidates = {
        "prompt": ("prompt", "question", "input", "text", "query", "instruction"),
        "external_id": ("external_id", "id", "case_id"),
        "raw_label": ("raw_label", "label", "category"),
        "normalized_risk_codes": ("normalized_risk_codes", "risk_category_code"),
        "system_prompt": ("system_prompt",),
        "language": ("language", "lang"),
    }

    def score(self, headers: set[str], file_name: str = "") -> float:
        # 兜底适配器：恒定低分，只在没有更匹配的适配器时被选中。
        return 0.3

    def normalize(
        self,
        row: dict[str, Any],
        row_number: int,
        file_name: str = "",
    ) -> CanonicalCase:
        view = RowIndex(row)
        prompt = view.get("prompt", "question", "input", "text", "query", "instruction")
        if not prompt:
            raise ValueError("missing prompt")

        labels = split_labels(view.get("raw_label", "label", "category"))
        codes = split_labels(view.get("normalized_risk_codes", "risk_category_code"))
        external_id = view.get("external_id", "id", "case_id") or f"case-{row_number}"

        consumed = (
            "prompt", "question", "input", "text", "query", "instruction",
            "external_id", "id", "case_id", "raw_label", "label", "category",
            "normalized_risk_codes", "risk_category_code",
            "system_prompt", "language", "lang", "metadata",
        )
        metadata = view.get("metadata")
        if not isinstance(metadata, dict):
            metadata = view.leftover(consumed)

        return CanonicalCase(
            external_id=str(external_id),
            prompt=str(prompt),
            system_prompt=str(view.get("system_prompt")) if view.get("system_prompt") else None,
            language=str(view.get("language", "lang") or "zh"),
            raw_labels=labels,
            risk_codes=codes,
            metadata=metadata,
        )
