import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db.models import Benchmark, BenchmarkVersion, TestCase
from app.schemas import BenchmarkImportError, BenchmarkImportResult
from app.services.base import BaseService
from app.services.dataset_adapters import CanonicalCase, detect_adapter
from app.services.storage import FileStorageService


class BenchmarkImportService(BaseService):
    def import_benchmark(
        self,
        *,
        name: str,
        version: str,
        content: bytes,
        file_name: str,
        mime_type: str | None = None,
        source_type: str | None = None,
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
        type_counts: dict[str, int] = {}
        for _, case, _ in valid_cases:
            type_counts[case.dataset_type] = type_counts.get(case.dataset_type, 0) + 1

        benchmark_version.case_count = len(valid_cases)
        benchmark_version.status = "ready" if valid_cases else "failed"
        benchmark.status = "active"
        self.uow.session.flush()

        return BenchmarkImportResult(
            benchmark_id=benchmark.id,
            benchmark_version_id=benchmark_version.id,
            imported_count=len(valid_cases),
            failed_count=len(errors),
            errors=errors,
            detected_adapter=match.adapter,
            adapter_display_name=match.display_name,
            adapter_confidence=match.confidence,
            field_mapping=match.field_mapping,
            dataset_type_counts=type_counts,
        )

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

        for parser in (self._parse_json, self._parse_jsonl, self._parse_csv):
            try:
                return parser(content)
            except Exception:
                continue
        raise ValueError("unsupported or invalid dataset file")

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
        rows = [
            (index, {key: value for key, value in item.items() if key is not None})
            for index, item in enumerate(reader, start=2)
        ]
        return rows, []

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
            dataset_type=case.dataset_type,
            sample_kind=case.sample_kind,
            case_metadata=case.metadata,
            content_hash=content_hash,
            status="active",
        )

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug[:120] if slug else f"benchmark-{uuid4().hex[:8]}"
