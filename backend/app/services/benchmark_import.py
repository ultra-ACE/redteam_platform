"""Benchmark 导入服务：异构适配 + 统一风险分类。

导入流程分三步，对应创新点一的三个层次：

1. 结构适配：由 dataset_adapters 按表头签名识别数据集来源（HarmBench /
   AdvBench / TDC2023 / 中文数据集 / 通用），把任意结构归一成 CanonicalCase，
   不再需要事先手工转成 JSONL。
2. 风险归一：把各家原始风险标签按「统一 code → 统一分类名 → 别名词典 →
   该 Benchmark 历史映射」的顺序映射到统一风险分类，并记录命中方式。
3. 入库：产出统一的 test_cases + test_case_risk_labels + benchmark_risk_mappings，
   后续评测链路完全与数据来源无关。
"""
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db.models import (
    Benchmark,
    BenchmarkRiskMapping,
    BenchmarkVersion,
    RiskCategory,
    TestCase,
    TestCaseRiskLabel,
)
from app.schemas import BenchmarkImportError, BenchmarkImportLabelMapping, BenchmarkImportResult
from app.services.base import BaseService
from app.services.dataset_adapters import CanonicalCase, detect_adapter
from app.services.risk_aliases import ensure_builtin_aliases, resolve_default_taxonomy_id
from app.services.storage import FileStorageService

UNLABELED_KEY = "(无风险标签)"
DEFAULT_KEY = "(默认类别兜底)"


def alias_key(value: Any) -> str:
    """别名词典归一化键：去首尾空白、转小写、压缩内部空白（保留点号与连字符）。"""
    return " ".join(str(value).strip().lower().split())


class BenchmarkImportService(BaseService):
    def import_benchmark(
        self,
        *,
        name: str,
        version: str,
        content: bytes,
        file_name: str,
        mime_type: str | None = None,
        risk_taxonomy_id: int | None = None,
        source_type: str | None = None,
        default_risk_category_code: str | None = None,
        base_dir: Path | None = None,
    ) -> BenchmarkImportResult:
        if not content:
            raise ValueError("dataset file is empty")

        raw_rows, errors = self._parse_rows(content, file_name)
        if not raw_rows:
            raise ValueError("no valid dataset rows found")

        adapter, match = detect_adapter(
            [item for _, item in raw_rows],
            file_name=file_name,
            explicit=source_type,
        )

        # 统一风险分类：确定目标风险体系，并补齐内置别名词典
        effective_taxonomy_id = risk_taxonomy_id or resolve_default_taxonomy_id(self.uow)
        if effective_taxonomy_id is not None:
            ensure_builtin_aliases(self.uow, effective_taxonomy_id)

        default_category = None
        if default_risk_category_code:
            default_category = self._find_category_by_code(
                default_risk_category_code, effective_taxonomy_id
            )
            if default_category is None:
                raise ValueError(f"默认风险类别不存在: {default_risk_category_code}")

        checksum = hashlib.sha256(content).hexdigest()
        stored_file = FileStorageService(self.uow).save_bytes(
            content=content,
            original_name=file_name,
            mime_type=mime_type,
            owner_type="benchmark_import",
            base_dir=base_dir,
        )
        benchmark = self._get_or_create_benchmark(name)
        existing = self.uow.benchmark_versions.list(
            page=1,
            page_size=1,
            benchmark_id=benchmark.id,
            version=version,
        )
        if existing:
            raise ValueError(f"benchmark version already exists: {benchmark.slug}/{version}")

        benchmark_version = BenchmarkVersion(
            benchmark_id=benchmark.id,
            version=version,
            source_file_id=stored_file.id,
            raw_schema={
                "adapter": match.adapter,
                "adapter_display_name": match.display_name,
                "adapter_confidence": match.confidence,
                "field_mapping": match.field_mapping,
                "source_file": file_name,
                "detection": match.note,
            },
            checksum=checksum,
            case_count=0,
            imported_at=datetime.now(timezone.utc),
            status="importing",
        )
        self.uow.benchmark_versions.add(benchmark_version)

        valid_cases: list[tuple[int, CanonicalCase, TestCase]] = []
        for row_number, item in raw_rows:
            try:
                case = adapter.normalize(item, row_number, file_name)
                test_case = self._build_test_case(benchmark_version.id, case)
                self.uow.test_cases.add(test_case)
                valid_cases.append((row_number, case, test_case))
            except Exception as exc:
                errors.append(BenchmarkImportError(row_number=row_number, message=str(exc)))

        self.uow.session.flush()

        unresolved: set[str] = set()
        label_stats: dict[str, dict[str, Any]] = {}
        resolution_cache: dict[str, tuple[RiskCategory | None, str | None]] = {}
        imported_count = 0
        unlabeled_count = 0

        for row_number, case, test_case in valid_cases:
            try:
                labels = list(dict.fromkeys(case.risk_codes + case.raw_labels))
                categories: list[RiskCategory] = []

                for label in labels:
                    category, matched_by = self._resolve_label(
                        label,
                        effective_taxonomy_id,
                        benchmark.id,
                        resolution_cache,
                    )
                    self._record_label_stat(label_stats, label, category, matched_by)
                    if category is None:
                        unresolved.add(label)
                    elif category not in categories:
                        categories.append(category)

                if not labels:
                    if default_category is not None:
                        categories = [default_category]
                        self._record_label_stat(label_stats, DEFAULT_KEY, default_category, "default")
                    else:
                        unlabeled_count += 1
                        self._record_label_stat(label_stats, UNLABELED_KEY, None, None)

                for category in categories:
                    self.uow.test_case_risk_labels.add(
                        TestCaseRiskLabel(
                            test_case_id=test_case.id,
                            risk_category_id=category.id,
                            label_source="benchmark",
                            is_primary=True,
                            confidence=1.0,
                        )
                    )
                    self._ensure_mapping(benchmark_version.id, case, category)
                imported_count += 1
            except Exception as exc:
                errors.append(BenchmarkImportError(row_number=row_number, message=str(exc)))

        benchmark_version.case_count = imported_count
        benchmark_version.status = "ready" if imported_count else "failed"
        benchmark.status = "active"
        self.uow.session.flush()

        return BenchmarkImportResult(
            benchmark_id=benchmark.id,
            benchmark_version_id=benchmark_version.id,
            imported_count=imported_count,
            failed_count=len(errors),
            unresolved_labels=sorted(unresolved),
            errors=errors,
            detected_adapter=match.adapter,
            adapter_display_name=match.display_name,
            adapter_confidence=match.confidence,
            field_mapping=match.field_mapping,
            label_mappings=self._build_label_mappings(label_stats),
            unlabeled_count=unlabeled_count,
        )

    # ---------- 解析 ----------

    def _parse_rows(
        self,
        content: bytes,
        file_name: str,
    ) -> tuple[list[tuple[int, dict[str, Any]]], list[BenchmarkImportError]]:
        suffix = Path(file_name).suffix.lower()
        try:
            if suffix in {".jsonl", ".ndjson"}:
                return self._parse_jsonl(content)
            if suffix == ".json":
                return self._parse_json(content)
            if suffix == ".csv":
                return self._parse_csv(content)
        except Exception as exc:
            raise ValueError(f"failed to parse dataset: {exc}") from exc

        try:
            return self._parse_json(content)
        except Exception:
            pass
        try:
            return self._parse_jsonl(content)
        except Exception:
            pass
        try:
            return self._parse_csv(content)
        except Exception as exc:
            raise ValueError(f"unsupported or invalid dataset file: {exc}") from exc

    def _parse_jsonl(self, content: bytes) -> tuple[list[tuple[int, dict[str, Any]]], list[BenchmarkImportError]]:
        rows: list[tuple[int, dict[str, Any]]] = []
        errors: list[BenchmarkImportError] = []
        for line_number, line in enumerate(content.decode("utf-8-sig").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError("row must be a JSON object")
                rows.append((line_number, item))
            except Exception as exc:
                errors.append(BenchmarkImportError(row_number=line_number, message=str(exc)))
        return rows, errors

    def _parse_json(self, content: bytes) -> tuple[list[tuple[int, dict[str, Any]]], list[BenchmarkImportError]]:
        payload = json.loads(content.decode("utf-8-sig"))
        if isinstance(payload, list):
            raw_rows = payload
        elif isinstance(payload, dict):
            raw_rows = payload.get("data") or payload.get("cases") or payload.get("items") or [payload]
        else:
            raise ValueError("json root must be an object or array")

        rows: list[tuple[int, dict[str, Any]]] = []
        errors: list[BenchmarkImportError] = []
        for index, item in enumerate(raw_rows, start=1):
            if not isinstance(item, dict):
                errors.append(BenchmarkImportError(row_number=index, message="row must be a JSON object"))
                continue
            rows.append((index, item))
        return rows, errors

    def _parse_csv(self, content: bytes) -> tuple[list[tuple[int, dict[str, Any]]], list[BenchmarkImportError]]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows: list[tuple[int, dict[str, Any]]] = []
        errors: list[BenchmarkImportError] = []
        for index, item in enumerate(reader, start=2):
            try:
                rows.append((index, {key: value for key, value in item.items() if key is not None}))
            except Exception as exc:
                errors.append(BenchmarkImportError(row_number=index, message=str(exc)))
        return rows, errors

    # ---------- 入库 ----------

    def _get_or_create_benchmark(self, name: str) -> Benchmark:
        slug = self._slugify(name)
        existing = self.uow.benchmarks.list(page=1, page_size=1, slug=slug)
        if existing:
            return existing[0]
        benchmark = Benchmark(
            name=name,
            slug=slug,
            source_type="imported",
            description=f"Imported from dataset: {name}",
            status="active",
        )
        return self.uow.benchmarks.add(benchmark)

    def _build_test_case(self, benchmark_version_id: int, case: CanonicalCase) -> TestCase:
        content_hash = hashlib.sha256(
            f"{case.system_prompt or ''}\n{case.prompt}".encode("utf-8")
        ).hexdigest()
        return TestCase(
            benchmark_version_id=benchmark_version_id,
            external_id=case.external_id[:128],
            prompt=case.prompt,
            system_prompt=case.system_prompt,
            language=(case.language or "zh")[:32],
            source_label=case.raw_labels[0] if case.raw_labels else None,
            case_metadata=case.metadata,
            content_hash=content_hash,
            status="active",
        )

    # ---------- 风险归一 ----------

    def _resolve_label(
        self,
        label: str,
        risk_taxonomy_id: int | None,
        benchmark_id: int,
        cache: dict[str, tuple[RiskCategory | None, str | None]],
    ) -> tuple[RiskCategory | None, str | None]:
        """四级解析：统一 code → 统一分类名 → 别名词典 → 该 Benchmark 历史映射。"""
        cache_key = f"{risk_taxonomy_id}:{benchmark_id}:{label}"
        if cache_key in cache:
            return cache[cache_key]

        category = self._find_category_by_code(label, risk_taxonomy_id)
        matched_by = "code" if category else None
        if category is None:
            category = self._find_category_by_name(label, risk_taxonomy_id)
            matched_by = "name" if category else None
        if category is None:
            category = self._find_by_alias(label, risk_taxonomy_id)
            matched_by = "alias" if category else None
        if category is None:
            category = self._find_by_benchmark_history(benchmark_id, label)
            matched_by = "benchmark_history" if category else None

        result = (category, matched_by)
        cache[cache_key] = result
        return result

    def _find_category_by_code(self, value: str, risk_taxonomy_id: int | None) -> RiskCategory | None:
        filters: dict[str, Any] = {"code": value}
        if risk_taxonomy_id is not None:
            filters["taxonomy_id"] = risk_taxonomy_id
        found = self.uow.risk_categories.list(page=1, page_size=1, **filters)
        return found[0] if found else None

    def _find_category_by_name(self, value: str, risk_taxonomy_id: int | None) -> RiskCategory | None:
        filters: dict[str, Any] = {"name": value}
        if risk_taxonomy_id is not None:
            filters["taxonomy_id"] = risk_taxonomy_id
        found = self.uow.risk_categories.list(page=1, page_size=1, **filters)
        return found[0] if found else None

    def _find_by_alias(self, value: str, risk_taxonomy_id: int | None) -> RiskCategory | None:
        filters: dict[str, Any] = {"alias": alias_key(value)}
        if risk_taxonomy_id is not None:
            filters["taxonomy_id"] = risk_taxonomy_id
        aliases = self.uow.risk_label_aliases.list(page=1, page_size=1, **filters)
        if not aliases:
            return None
        return self.uow.risk_categories.get(aliases[0].risk_category_id)

    def _find_by_benchmark_history(self, benchmark_id: int, value: str) -> RiskCategory | None:
        """同一 Benchmark 的历史版本若已映射过该标签，新版本自动继承，避免重复人工映射。"""
        versions = self.uow.benchmark_versions.list(
            page=1,
            page_size=50,
            benchmark_id=benchmark_id,
            order_by=BenchmarkVersion.id.desc(),
        )
        for version in versions:
            mappings = self.uow.benchmark_risk_mappings.list(
                page=1,
                page_size=1,
                benchmark_version_id=version.id,
                raw_label=value,
            )
            if mappings:
                return self.uow.risk_categories.get(mappings[0].risk_category_id)
        return None

    def _ensure_mapping(
        self,
        benchmark_version_id: int,
        case: CanonicalCase,
        category: RiskCategory,
    ) -> None:
        for raw_label in case.raw_labels:
            existing = self.uow.benchmark_risk_mappings.list(
                page=1,
                page_size=1,
                benchmark_version_id=benchmark_version_id,
                raw_label=raw_label,
                risk_category_id=category.id,
            )
            if existing:
                continue
            self.uow.benchmark_risk_mappings.add(
                BenchmarkRiskMapping(
                    benchmark_version_id=benchmark_version_id,
                    raw_label=raw_label,
                    risk_category_id=category.id,
                    mapping_type="auto",
                    confidence=1.0,
                    mapping_note="Auto mapped during benchmark import",
                )
            )

    # ---------- 导入报告 ----------

    @staticmethod
    def _record_label_stat(
        stats: dict[str, dict[str, Any]],
        label: str,
        category: RiskCategory | None,
        matched_by: str | None,
    ) -> None:
        entry = stats.setdefault(
            label,
            {"count": 0, "category": category, "matched_by": matched_by},
        )
        entry["count"] += 1
        if entry["category"] is None and category is not None:
            entry["category"] = category
            entry["matched_by"] = matched_by

    @staticmethod
    def _build_label_mappings(stats: dict[str, dict[str, Any]]) -> list[BenchmarkImportLabelMapping]:
        mappings: list[BenchmarkImportLabelMapping] = []
        for label, entry in stats.items():
            category = entry["category"]
            mappings.append(
                BenchmarkImportLabelMapping(
                    raw_label=label,
                    risk_category_id=category.id if category else None,
                    risk_category_code=category.code if category else None,
                    risk_category_name=category.name if category else None,
                    matched_by=entry["matched_by"],
                    case_count=int(entry["count"]),
                )
            )
        mappings.sort(key=lambda item: (-item.case_count, item.raw_label))
        return mappings

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if slug:
            return slug[:120]
        return f"benchmark-{uuid4().hex[:8]}"
