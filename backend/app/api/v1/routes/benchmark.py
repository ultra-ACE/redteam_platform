from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import (
    ApiResponse,
    Benchmark,
    BenchmarkVersion,
    PaginatedData,
    TestCase,
    TestCaseUpdateRequest,
)
from app.services import BenchmarkImportService, BenchmarkService, UnitOfWork
from app.services.dataset_adapters import list_adapters

router = APIRouter()


@router.post(
    "/benchmarks/import",
    response_model=ApiResponse[dict[str, Any]],
    operation_id="importBenchmark",
    tags=["Benchmark"],
)
async def import_benchmark(
    name: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    risk_taxonomy_id: int | None = Form(default=None),
    source_type: str | None = Form(default=None),
    default_risk_category_code: str | None = Form(default=None),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    safe_name = (name or "").strip()
    if not safe_name or safe_name.lower() == "undefined":
        raise HTTPException(status_code=422, detail="benchmark name is required")
    safe_version = (version or "").strip()
    if not safe_version or safe_version.lower() == "undefined":
        raise HTTPException(status_code=422, detail="benchmark version is required")

    content = await file.read()
    try:
        result = BenchmarkImportService(uow).import_benchmark(
            name=safe_name,
            version=safe_version,
            content=content,
            file_name=file.filename or "dataset.jsonl",
            mime_type=file.content_type,
            risk_taxonomy_id=risk_taxonomy_id,
            source_type=(source_type or "").strip() or None,
            default_risk_category_code=(default_risk_category_code or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(result.model_dump())


@router.get(
    "/benchmarks/adapters",
    response_model=ApiResponse[list[dict[str, Any]]],
    operation_id="listBenchmarkAdapters",
    tags=["Benchmark"],
)
async def list_benchmark_adapters(
    _: None = Depends(require_local_token),
) -> dict:
    """列出内置的异构数据集适配器，导入时可据此手动指定 source_type。"""
    return ok(list_adapters())


@router.get(
    "/benchmarks",
    response_model=ApiResponse[PaginatedData[Benchmark]],
    operation_id="listBenchmarks",
    tags=["Benchmark"],
)
async def list_benchmarks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
    status: str | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = BenchmarkService(uow)
    items = service.list_benchmarks(page=page, page_size=page_size, keyword=keyword, status=status)
    total = uow.benchmarks.count(status=status)
    return ok(PaginatedData[Benchmark](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.get(
    "/benchmarks/{benchmark_id}/versions",
    response_model=ApiResponse[PaginatedData[BenchmarkVersion]],
    operation_id="listBenchmarkVersions",
    tags=["Benchmark"],
)
async def list_benchmark_versions(
    benchmark_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = BenchmarkService(uow)
    items = service.list_versions(benchmark_id=benchmark_id, page=page, page_size=page_size)
    total = uow.benchmark_versions.count(benchmark_id=benchmark_id)
    return ok(PaginatedData[BenchmarkVersion](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.get(
    "/test-cases",
    response_model=ApiResponse[PaginatedData[TestCase]],
    operation_id="listTestCases",
    tags=["测试用例"],
)
async def list_test_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    benchmark_version_id: int | None = None,
    risk_category_code: str | None = None,
    status: str | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = BenchmarkService(uow)
    items = service.list_test_cases(
        page=page,
        page_size=page_size,
        benchmark_version_id=benchmark_version_id,
        status=status,
    )
    total = uow.test_cases.count(benchmark_version_id=benchmark_version_id, status=status)
    return ok(PaginatedData[TestCase](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.patch(
    "/test-cases/{test_case_id}",
    response_model=ApiResponse[TestCase],
    operation_id="updateTestCase",
    tags=["测试用例"],
)
async def update_test_case(
    test_case_id: int,
    payload: TestCaseUpdateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = BenchmarkService(uow)
    test_case = service.update_test_case(test_case_id, payload)
    if test_case is None:
        raise HTTPException(status_code=404, detail="test case not found")
    return ok(TestCase.model_validate(test_case).model_dump())


@router.delete(
    "/benchmark-versions/{benchmark_version_id}",
    response_model=ApiResponse[dict[str, int]],
    operation_id="deleteBenchmarkVersion",
    tags=["Benchmark"],
)
async def delete_benchmark_version(
    benchmark_version_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    try:
        summary = BenchmarkService(uow).delete_version(benchmark_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if summary is None:
        raise HTTPException(status_code=404, detail="benchmark version not found")
    return ok(summary)


@router.delete(
    "/benchmarks/{benchmark_id}",
    response_model=ApiResponse[dict[str, int]],
    operation_id="deleteBenchmark",
    tags=["Benchmark"],
)
async def delete_benchmark(
    benchmark_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    try:
        summary = BenchmarkService(uow).delete_benchmark(benchmark_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if summary is None:
        raise HTTPException(status_code=404, detail="benchmark not found")
    return ok(summary)

