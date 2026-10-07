from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import ApiResponse, Report, ReportCreateRequest
from app.services import ReportService, UnitOfWork
from app.workers.queue import enqueue_report

router = APIRouter(tags=["报告"])


@router.post(
    "/reports",
    response_model=ApiResponse[Report],
    operation_id="createReport",
)
async def create_report(
    payload: ReportCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportService(uow)
    report = service.create_report(payload)
    uow.commit()
    enqueue_report(report.id)
    return ok(Report.model_validate(report).model_dump())


@router.get(
    "/reports/{report_id}",
    response_model=ApiResponse[Report],
    operation_id="getReport",
)
async def get_report(
    report_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = ReportService(uow)
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return ok(Report.model_validate(report).model_dump())


@router.get(
    "/reports/{report_id}/download",
    operation_id="downloadReport",
)
async def download_report(
    report_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> FileResponse:
    service = ReportService(uow)
    info = service.get_download_info(report_id)
    if info is None:
        raise HTTPException(status_code=404, detail="report file not ready")
    path = Path(info["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="report file not found")
    return FileResponse(
        path=path,
        media_type=info["mime_type"],
        filename=info["filename"],
    )
