"""数据集适配器注册表：负责自动识别与显式指定。

识别策略：用前若干行的字段名生成"表头签名"，让每个适配器打分，取最高分。
调用方也可以通过 ``source_type`` 参数显式指定适配器，跳过自动识别。
"""
from typing import Any

from app.services.dataset_adapters.base import AdapterMatch, DatasetAdapter, header_keys
from app.services.dataset_adapters.behavior_csv import BehaviorCsvAdapter
from app.services.dataset_adapters.chinese import ChineseGenericAdapter
from app.services.dataset_adapters.generic import GenericAdapter
from app.services.dataset_adapters.harmbench import HarmBenchAdapter

ADAPTERS: tuple[DatasetAdapter, ...] = (
    HarmBenchAdapter(),
    BehaviorCsvAdapter(),
    ChineseGenericAdapter(),
    GenericAdapter(),
)

GENERIC_ADAPTER = ADAPTERS[-1]


def list_adapters() -> list[dict[str, str]]:
    return [
        {
            "name": adapter.name,
            "display_name": adapter.display_name,
            "description": adapter.description,
        }
        for adapter in ADAPTERS
    ]


def get_adapter(name: str) -> DatasetAdapter | None:
    for adapter in ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


def detect_adapter(
    rows: list[dict[str, Any]],
    file_name: str = "",
    explicit: str | None = None,
) -> tuple[DatasetAdapter, AdapterMatch]:
    headers = header_keys(rows)

    if explicit:
        adapter = get_adapter(explicit)
        if adapter is None:
            supported = ", ".join(item.name for item in ADAPTERS)
            raise ValueError(f"未知的数据集适配器: {explicit}（可用: {supported}）")
        return adapter, AdapterMatch(
            adapter=adapter.name,
            display_name=adapter.display_name,
            confidence=1.0,
            field_mapping=adapter.mapping(headers),
            note="由导入参数 source_type 显式指定",
        )

    scored = [(adapter.score(headers, file_name), adapter) for adapter in ADAPTERS]
    best_score, best_adapter = max(scored, key=lambda item: item[0])
    if best_score <= 0:
        best_score, best_adapter = 0.0, GENERIC_ADAPTER

    return best_adapter, AdapterMatch(
        adapter=best_adapter.name,
        display_name=best_adapter.display_name,
        confidence=round(float(best_score), 4),
        field_mapping=best_adapter.mapping(headers),
        note="按表头签名自动识别",
    )
