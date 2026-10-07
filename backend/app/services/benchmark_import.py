import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db.models import Benchmark, BenchmarkRiskMapping, BenchmarkVersion, RiskCategory, TestCase, TestCaseRiskLabel
from app.schemas import BenchmarkImportError, BenchmarkImportResult
from app.services.base import BaseService
from app.services.storage import FileStorageService

KNOWN_FIELDS = {
    "external_id",
    "id",
    "case_id",
    "prompt",
    "question",
    "input",
    "text",
    "system_prompt",
    "language",
    "lang",
    "raw_label",
    "label",
    "category",
    "normalized_risk_codes",
    "risk_category_code",
    "metadata",
}


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
        base_dir: Path | None = None,
    ) -> BenchmarkImportResult:
        if not content:
            raise ValueError("dataset file is empty")

        rows, errors = self._parse_rows(content, file_name)
        if not rows:
            raise ValueError("no valid dataset rows found")

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
            checksum=checksum,
            case_count=0,
            imported_at=datetime.now(timezone.utc),
            status="importing",
        )
        self.uow.benchmark_versions.add(benchmark_version)

        valid_cases: list[tuple[int, dict[str, Any], TestCase]] = []
        for row_number, item in rows:
            try:
                test_case = self._build_test_case(benchmark_version.id, row_number, item)
                self.uow.test_cases.add(test_case)
                valid_cases.append((row_number, item, test_case))
            except Exception as exc:
                errors.append(BenchmarkImportError(row_number=row_number, message=str(exc)))

        self.uow.session.flush()

        unresolved: set[str] = set()
        imported_count = 0
        for row_number, item, test_case in valid_cases:
            try:
                categories = self._resolve_categories(item, risk_taxonomy_id)
                if not categories:
                    unresolved.update(self._raw_labels(item))
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
                    self._ensure_mapping(benchmark_version.id, item, category)
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
        )

    def _parse_rows(self, content: bytes, file_name: str) -> tuple[list[tuple[int, dict[str, Any]]], list[BenchmarkImportError]]:
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

    def _build_test_case(self, benchmark_version_id: int, row_number: int, item: dict[str, Any]) -> TestCase:
        prompt = item.get("prompt") or item.get("question") or item.get("input") or item.get("text")
        if not prompt:
            raise ValueError("missing prompt")
        system_prompt = item.get("system_prompt")
        external_id = str(item.get("external_id") or item.get("id") or item.get("case_id") or f"case-{row_number}")
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {key: value for key, value in item.items() if key not in KNOWN_FIELDS}
        content_hash = hashlib.sha256(
            f"{system_prompt or ''}\n{prompt}".encode("utf-8")
        ).hexdigest()
        return TestCase(
            benchmark_version_id=benchmark_version_id,
            external_id=external_id,
            prompt=str(prompt),
            system_prompt=str(system_prompt) if system_prompt else None,
            language=str(item.get("language") or item.get("lang") or "zh"),
            source_label=self._raw_label(item),
            case_metadata=metadata,
            content_hash=content_hash,
            status="active",
        )

    def _resolve_categories(self, item: dict[str, Any], risk_taxonomy_id: int | None) -> list[RiskCategory]:
        codes = item.get("normalized_risk_codes") or []
        if isinstance(codes, str):
            codes = [code.strip() for code in codes.split(",") if code.strip()]
        codes = list(codes)
        single_code = item.get("risk_category_code")
        if single_code and single_code not in codes:
            codes.append(single_code)
        if not codes:
            raw_label = self._raw_label(item)
            if raw_label:
                codes = [raw_label]

        categories: list[RiskCategory] = []
        seen: set[int] = set()
        for code in codes:
            category = self._find_category(str(code), risk_taxonomy_id)
            if category is not None and category.id not in seen:
                categories.append(category)
                seen.add(category.id)
        return categories

    def _find_category(self, value: str, risk_taxonomy_id: int | None) -> RiskCategory | None:
        filters: dict[str, Any] = {"page": 1, "page_size": 1}
        if risk_taxonomy_id is not None:
            filters["taxonomy_id"] = risk_taxonomy_id
        by_code = self.uow.risk_categories.list(code=value, **filters)
        if by_code:
            return by_code[0]
        by_name = self.uow.risk_categories.list(name=value, **filters)
        return by_name[0] if by_name else None

    def _ensure_mapping(self, benchmark_version_id: int, item: dict[str, Any], category: RiskCategory) -> None:
        for raw_label in self._raw_labels(item):
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

    def _raw_labels(self, item: dict[str, Any]) -> list[str]:
        value = item.get("raw_label") or item.get("label") or item.get("category")
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value:
            return [str(value).strip()]
        codes = item.get("normalized_risk_codes") or []
        if isinstance(codes, str):
            return [code.strip() for code in codes.split(",") if code.strip()]
        if isinstance(codes, list):
            return [str(code).strip() for code in codes if str(code).strip()]
        return []

    def _raw_label(self, item: dict[str, Any]) -> str | None:
        labels = self._raw_labels(item)
        return labels[0] if labels else None

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if slug:
            return slug[:120]
        return f"benchmark-{uuid4().hex[:8]}"
