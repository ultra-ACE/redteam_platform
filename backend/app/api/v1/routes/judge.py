from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_uow
from app.api.utils import ok, require_local_token
from app.schemas import (
    ApiResponse,
    JudgeProfile,
    JudgeProfileCreateRequest,
    JudgeProfileUpdateRequest,
    JudgeReEvaluateResult,
    JudgeTrustSummary,
    JudgeType,
    PaginatedData,
)
from app.services import JudgeManagementService, UnitOfWork
from app.services.judge_eval import JudgeEvaluationService

router = APIRouter(tags=["Judge"])


@router.get(
    "/judge-profiles/rule-defaults",
    response_model=ApiResponse[dict[str, Any]],
    operation_id="getRuleJudgeDefaults",
)
async def get_rule_judge_defaults(
    _: None = Depends(require_local_token),
) -> dict:
    """返回规则 Judge 的内置默认关键词，供前端「填入默认关键词」使用。"""
    return ok(
        {
            "harmful_keywords": list(JudgeEvaluationService.HARMFUL_KEYWORDS),
            "refusal_keywords": list(JudgeEvaluationService.REFUSAL_KEYWORDS),
            "harmful_patterns": [],
            "unsafe_confidence": 0.8,
            "safe_confidence": 0.8,
            "uncertain_confidence": 0.5,
        }
    )


@router.get(
    "/judge-profiles",
    response_model=ApiResponse[PaginatedData[JudgeProfile]],
    operation_id="listJudgeProfiles",
)
async def list_judge_profiles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    judge_type: JudgeType | None = None,
    enabled: bool | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = JudgeManagementService(uow)
    items = service.list_profiles(page=page, page_size=page_size, judge_type=judge_type, enabled=enabled)
    total = uow.judge_profiles.count(judge_type=judge_type, enabled=enabled)
    return ok(PaginatedData[JudgeProfile](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.post(
    "/judge-profiles",
    response_model=ApiResponse[JudgeProfile],
    operation_id="createJudgeProfile",
)
async def create_judge_profile(
    payload: JudgeProfileCreateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    profile = JudgeManagementService(uow).create_profile(payload)
    return ok(JudgeProfile.model_validate(profile).model_dump())


@router.get(
    "/judge-profiles/{profile_id}",
    response_model=ApiResponse[JudgeProfile],
    operation_id="getJudgeProfile",
)
async def get_judge_profile(
    profile_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    profile = JudgeManagementService(uow).get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="judge profile not found")
    return ok(JudgeProfile.model_validate(profile).model_dump())


@router.patch(
    "/judge-profiles/{profile_id}",
    response_model=ApiResponse[JudgeProfile],
    operation_id="updateJudgeProfile",
)
async def update_judge_profile(
    profile_id: int,
    payload: JudgeProfileUpdateRequest,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    profile = JudgeManagementService(uow).update_profile(profile_id, payload)
    if profile is None:
        raise HTTPException(status_code=404, detail="judge profile not found")
    return ok(JudgeProfile.model_validate(profile).model_dump())


@router.delete(
    "/judge-profiles/{profile_id}",
    response_model=ApiResponse[JudgeProfile],
    operation_id="disableJudgeProfile",
)
async def disable_judge_profile(
    profile_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    profile = JudgeManagementService(uow).disable_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="judge profile not found")
    return ok(JudgeProfile.model_validate(profile).model_dump())


@router.get(
    "/evaluation-tasks/{task_id}/judge-trust",
    response_model=ApiResponse[JudgeTrustSummary],
    operation_id="getJudgeTrust",
)
async def get_judge_trust(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    summary = JudgeManagementService(uow).get_trust_summary(task_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(summary.model_dump())


@router.post(
    "/judge-results/{judge_result_id}/re-evaluate",
    response_model=ApiResponse[JudgeReEvaluateResult],
    operation_id="reEvaluateJudgeResult",
)
async def re_evaluate_judge_result(
    judge_result_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    result = JudgeManagementService(uow).re_evaluate(judge_result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="judge result not found")
    return ok(
        JudgeReEvaluateResult(
            judge_result_id=result.id,
            status=result.status,
            verdict=result.verdict,
            trust_score=result.trust_score,
        ).model_dump()
    )
