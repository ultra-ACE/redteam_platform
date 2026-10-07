from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import (
    ApiResponse,
    PaginatedData,
    RiskAssessment,
    RiskCategory,
    RiskCategoryCreateRequest,
    RiskMappingBatchRequest,
    RiskMappingBatchResult,
    RiskMappingStatus,
    RiskTaxonomy,
    RiskTaxonomyCreateRequest,
)
from app.services import RiskMappingService, StatisticsService, UnitOfWork

router = APIRouter()


@router.get(
    "/risk-taxonomies",
    response_model=ApiResponse[PaginatedData[RiskTaxonomy]],
    operation_id="listRiskTaxonomies",
    tags=["风险分类"],
)
async def list_risk_taxonomies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = RiskMappingService(uow)
    items = service.list_taxonomies(page=page, page_size=page_size)
    total = uow.risk_taxonomies.count()
    return ok(PaginatedData[RiskTaxonomy](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/risk-taxonomies",
    response_model=ApiResponse[RiskTaxonomy],
    operation_id="createRiskTaxonomy",
    tags=["风险分类"],
)
async def create_risk_taxonomy(
    payload: RiskTaxonomyCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    taxonomy = RiskMappingService(uow).create_taxonomy(payload)
    return ok(RiskTaxonomy.model_validate(taxonomy).model_dump())


@router.get(
    "/risk-taxonomies/{taxonomy_id}/categories",
    response_model=ApiResponse[list[RiskCategory]],
    operation_id="listRiskCategories",
    tags=["风险分类"],
)
async def list_risk_categories(
    taxonomy_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    items = RiskMappingService(uow).list_category_tree(taxonomy_id)
    return ok([item.model_dump() for item in items])


@router.post(
    "/risk-taxonomies/{taxonomy_id}/categories",
    response_model=ApiResponse[RiskCategory],
    operation_id="createRiskCategory",
    tags=["风险分类"],
)
async def create_risk_category(
    taxonomy_id: int,
    payload: RiskCategoryCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    category = RiskMappingService(uow).create_category(taxonomy_id, payload)
    return ok(category.model_dump())


@router.post(
    "/benchmark-versions/{benchmark_version_id}/risk-mappings/batch",
    response_model=ApiResponse[RiskMappingBatchResult],
    operation_id="batchUpsertRiskMappings",
    tags=["风险分类"],
)
async def batch_upsert_risk_mappings(
    benchmark_version_id: int,
    payload: RiskMappingBatchRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    result = RiskMappingService(uow).batch_upsert_mappings(benchmark_version_id, payload.mappings)
    return ok(result.model_dump())


@router.get(
    "/benchmark-versions/{benchmark_version_id}/mapping-status",
    response_model=ApiResponse[RiskMappingStatus],
    operation_id="getRiskMappingStatus",
    tags=["风险分类"],
)
async def get_risk_mapping_status(
    benchmark_version_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    status = RiskMappingService(uow).get_mapping_status(benchmark_version_id)
    return ok(status.model_dump())


@router.get(
    "/task-attempts/{attempt_id}/risk",
    response_model=ApiResponse[RiskAssessment],
    operation_id="getTaskAttemptRisk",
    tags=["风险量化"],
)
async def get_task_attempt_risk(
    attempt_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    assessment = RiskMappingService(uow).get_assessment(attempt_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="risk assessment not found")
    return ok(assessment.model_dump())


@router.get(
    "/evaluation-tasks/{task_id}/risk-summary",
    response_model=ApiResponse[dict[str, Any]],
    operation_id="getRiskSummary",
    tags=["风险量化"],
)
async def get_risk_summary(
    task_id: int,
    risk_level: str | None = None,
    risk_category_code: str | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    stats = StatisticsService(uow).get_task_statistics(task_id)
    if stats is None:
        return ok({"task_id": task_id, "average_score": 0, "levels": {}, "categories": []})
    return ok(
        {
            "task_id": task_id,
            "average_score": stats.average_risk_score,
            "levels": stats.risk_level_distribution,
            "categories": stats.risk_category_distribution,
        }
    )
