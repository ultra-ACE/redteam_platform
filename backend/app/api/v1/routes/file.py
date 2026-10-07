from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_uow
from app.db.models import StoredFile as StoredFileModel
from app.api.utils import ok, require_local_token
from app.schemas import ApiResponse, PaginatedData, StoredFile
from app.services import FileStorageService, UnitOfWork

router = APIRouter(tags=["文件"])


@router.get(
    "/files",
    response_model=ApiResponse[PaginatedData[StoredFile]],
    operation_id="listFiles",
)
async def list_files(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    owner_type: str | None = None,
    owner_id: int | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    items = uow.files.list(
        page=page,
        page_size=page_size,
        owner_type=owner_type,
        owner_id=owner_id,
        order_by=StoredFileModel.created_at.desc(),
    )
    total = uow.files.count(owner_type=owner_type, owner_id=owner_id)
    return ok(PaginatedData[StoredFile](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/files",
    response_model=ApiResponse[StoredFile],
    operation_id="uploadFile",
)
async def upload_file(
    file: UploadFile = File(...),
    owner_type: str | None = Form(default=None),
    owner_id: int | None = Form(default=None),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    content = await file.read()
    try:
        stored = FileStorageService(uow).save_bytes(
            content=content,
            original_name=file.filename or "upload.bin",
            mime_type=file.content_type,
            owner_type=owner_type,
            owner_id=owner_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413 if "exceeds limit" in str(exc) else 422, detail=str(exc)) from exc
    return ok(StoredFile.model_validate(stored).model_dump())


@router.get(
    "/files/{file_id}",
    response_model=ApiResponse[StoredFile],
    operation_id="getFile",
)
async def get_file(
    file_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    stored = uow.files.get(file_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="file not found")
    return ok(StoredFile.model_validate(stored).model_dump())


@router.get(
    "/files/{file_id}/download",
    operation_id="downloadFile",
)
async def download_file(
    file_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> FileResponse:
    stored = uow.files.get(file_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="file not found")
    path = Path(stored.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing on disk")
    return FileResponse(
        path=path,
        media_type=stored.mime_type or "application/octet-stream",
        filename=stored.original_name,
    )
