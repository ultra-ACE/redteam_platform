from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_uow
from app.api.utils import get_operator, ok, require_local_token
from app.schemas import (
    ApiResponse,
    ManualReview,
    ManualReviewCreateRequest,
    ManualReviewDetail,
    ManualReviewUpdateRequest,
    PaginatedData,
)
from app.services import ManualReviewService, UnitOfWork

router = APIRouter(tags=["人工复核"])


@router.get(
    "/manual-reviews",
    response_model=ApiResponse[PaginatedData[ManualReview]],
    operation_id="listManualReviews",
)
async def list_manual_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = None,
    trigger_reason: str | None = None,
    task_id: int | None = None,
    task_attempt_id: int | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    items, total = ManualReviewService(uow).list_reviews(
        page=page,
        page_size=page_size,
        status=status,
        trigger_reason=trigger_reason,
        task_id=task_id,
        task_attempt_id=task_attempt_id,
    )
    return ok(PaginatedData[ManualReview](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.get(
    "/manual-reviews/{review_id}",
    response_model=ApiResponse[ManualReviewDetail],
    operation_id="getManualReview",
)
async def get_manual_review(
    review_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    detail = ManualReviewService(uow).get_detail(review_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="manual review not found")
    return ok(detail.model_dump())


@router.post(
    "/manual-reviews",
    response_model=ApiResponse[ManualReviewDetail],
    operation_id="createManualReview",
)
async def create_manual_review(
    payload: ManualReviewCreateRequest,
    reviewer: str = Depends(get_operator),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    detail = ManualReviewService(uow).create_or_update(payload, reviewer=reviewer)
    return ok(detail.model_dump())


@router.patch(
    "/manual-reviews/{review_id}",
    response_model=ApiResponse[ManualReviewDetail],
    operation_id="updateManualReview",
)
async def update_manual_review(
    review_id: int,
    payload: ManualReviewUpdateRequest,
    reviewer: str = Depends(get_operator),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    detail = ManualReviewService(uow).update_review(review_id, payload, reviewer=reviewer)
    if detail is None:
        raise HTTPException(status_code=404, detail="manual review not found")
    return ok(detail.model_dump())
