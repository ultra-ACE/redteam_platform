"""异构 Benchmark 数据集适配层。

各家 Benchmark 的字段名、标签体系和文件结构都不一样（HarmBench 用 ``Behavior`` /
``SemanticCategory``，AdvBench 用 ``Behavior`` / ``Category``，中文数据集用
``提示词`` / ``风险类型``）。适配器负责：

1. ``score()``：依据表头签名自动识别数据集来源；
2. ``normalize()``：把任意结构的一行归一化成统一的 :class:`CanonicalCase`。

这样"异构适配"发生在系统内部，后续的风险归一与标准化评测只面对同一种数据结构。
"""
from dataclasses import dataclass, field
from typing import Any

SEPARATORS = (";", "|", "，", "、", "；")


def normalize_key(key: Any) -> str:
    """把字段名归一成比较键：去 BOM、去空白与分隔符、转小写。"""
    if not isinstance(key, str):
        return str(key)
    cleaned = key.strip().lstrip("\ufeff").lower()
    for char in (" ", "\t", "_", "-", "."):
        cleaned = cleaned.replace(char, "")
    return cleaned


def clean_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def split_labels(value: Any) -> list[str]:
    """把标签字段拆成列表，兼容中英文分隔符。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(item) for item in value]
    else:
        text = str(value)
        for separator in SEPARATORS:
            text = text.replace(separator, ",")
        items = text.split(",")
    return [item.strip() for item in items if item.strip()]


class RowIndex:
    """按归一化字段名读取一行数据，屏蔽大小写、下划线与空格差异。"""

    __slots__ = ("_values", "_original_keys")

    def __init__(self, row: dict[str, Any]) -> None:
        self._values: dict[str, Any] = {}
        self._original_keys: dict[str, str] = {}
        for key, value in row.items():
            normalized = normalize_key(key)
            if normalized and normalized not in self._values:
                self._values[normalized] = value
                self._original_keys[normalized] = key if isinstance(key, str) else str(key)

    def get(self, *names: str) -> Any:
        for name in names:
            value = clean_value(self._values.get(normalize_key(name)))
            if value is not None:
                return value
        return None

    def original_key(self, name: str) -> str:
        return self._original_keys.get(normalize_key(name), name)

    def leftover(self, consumed: tuple[str, ...]) -> dict[str, Any]:
        """返回未被适配器消费的原始字段，用于保留 metadata。"""
        consumed_keys = {normalize_key(name) for name in consumed}
        result: dict[str, Any] = {}
        for normalized, value in self._values.items():
            if normalized in consumed_keys:
                continue
            cleaned = clean_value(value)
            if cleaned is None:
                continue
            result[self._original_keys.get(normalized, normalized)] = cleaned
        return result


def header_keys(rows: list[dict[str, Any]], limit: int = 50) -> set[str]:
    """汇总前若干行的字段名（归一化后），用于适配器打分。"""
    keys: set[str] = set()
    for row in rows[:limit]:
        for key in row:
            normalized = normalize_key(key)
            if normalized:
                keys.add(normalized)
    return keys


def safe_external_id(
    value: Any,
    fallback: str,
    prompt: Any = None,
    max_length: int = 120,
) -> tuple[str, str | None]:
    """外部用例 ID 需要短且唯一。

    有些数据集（例如 TDC2023）把 ``BehaviorID`` 写成了整段 Behavior 文本的重复，
    直接入库既超长又无意义。这里在"留原值"和"退回生成值"之间做判断：

    返回 ``(最终 external_id, 被替换掉的原始值或 None)``。
    """
    if value is None:
        return fallback, None
    text = str(value).strip()
    if not text:
        return fallback, None
    if prompt is not None and text.lower() == str(prompt).strip().lower():
        return fallback, text
    if len(text) > max_length:
        return fallback, text
    return text, None


@dataclass
class CanonicalCase:
    """统一测试用例结构，导入之后的所有环节只依赖它。"""

    external_id: str
    prompt: str
    system_prompt: str | None = None
    language: str | None = None
    raw_labels: list[str] = field(default_factory=list)
    risk_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterMatch:
    """识别结果，用于导入报告展示"识别成什么、字段怎么映射的"。"""

    adapter: str
    display_name: str
    confidence: float
    field_mapping: dict[str, str] = field(default_factory=dict)
    note: str | None = None


class DatasetAdapter:
    name = "generic"
    display_name = "通用数据集"
    description = ""
    #: 统一字段 -> 该适配器可识别的原始字段名（用于生成导入报告的字段映射）
    field_candidates: dict[str, tuple[str, ...]] = {}

    def score(self, headers: set[str], file_name: str = "") -> float:
        """返回 0~1 的匹配度，0 表示不匹配。"""
        return 0.0

    def mapping(self, headers: set[str]) -> dict[str, str]:
        """返回「原始字段 -> 统一字段」，只保留实际出现在文件里的字段。"""
        result: dict[str, str] = {}
        for canonical, candidates in self.field_candidates.items():
            for candidate in candidates:
                if normalize_key(candidate) in headers:
                    result[candidate] = canonical
                    break
        return result

    def normalize(
        self,
        row: dict[str, Any],
        row_number: int,
        file_name: str = "",
    ) -> CanonicalCase:
        raise NotImplementedError
