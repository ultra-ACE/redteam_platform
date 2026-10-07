from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import (
    ApiResponse,
    PaginatedData,
    ReportTemplate,
    ReportTemplateCreateRequest,
    ReportTemplateVersion,
    ReportTemplateVersionCreateRequest,
)
from app.services import ReportTemplateService, UnitOfWork

router = APIRouter(tags=["报告模板"])


@router.get(
    "/report-templates",
    response_model=ApiResponse[PaginatedData[ReportTemplate]],
    operation_id="listReportTemplates",
)
async def list_report_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportTemplateService(uow)
    items = service.list_templates(page=page, page_size=page_size)
    total = uow.report_templates.count()
    return ok(PaginatedData[ReportTemplate](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/report-templates",
    response_model=ApiResponse[ReportTemplate],
    operation_id="createReportTemplate",
)
async def create_report_template(
    payload: ReportTemplateCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportTemplateService(uow)
    template = service.create_template(payload)
    return ok(ReportTemplate.model_validate(template).model_dump())


@router.get(
    "/report-templates/{template_id}/versions",
    response_model=ApiResponse[PaginatedData[ReportTemplateVersion]],
    operation_id="listReportTemplateVersions",
)
async def list_report_template_versions(
    template_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportTemplateService(uow)
    items = service.list_versions(template_id, page=page, page_size=page_size)
    total = uow.report_template_versions.count(template_id=template_id)
    return ok(
        PaginatedData[ReportTemplateVersion](
            items=items,
            page=page,
            page_size=page_size,
            total=total,
        ).model_dump()
    )


@router.post(
    "/report-templates/{template_id}/versions",
    response_model=ApiResponse[ReportTemplateVersion],
    operation_id="createReportTemplateVersion",
)
async def create_report_template_version(
    template_id: int,
    payload: ReportTemplateVersionCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportTemplateService(uow)
    version = service.create_version(template_id, payload)
    return ok(ReportTemplateVersion.model_validate(version).model_dump())


@router.get(
    "/report-template-versions/{version_id}",
    response_model=ApiResponse[ReportTemplateVersion],
    operation_id="getReportTemplateVersion",
)
async def get_report_template_version(
    version_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportTemplateService(uow)
    version = service.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="report template version not found")
    return ok(ReportTemplateVersion.model_validate(version).model_dump())


@router.post(
    "/report-template-versions/{version_id}/publish",
    response_model=ApiResponse[ReportTemplateVersion],
    operation_id="publishReportTemplateVersion",
)
async def publish_report_template_version(
    version_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportTemplateService(uow)
    version = service.publish_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="report template version not found")
    return ok(ReportTemplateVersion.model_validate(version).model_dump())
