import json
from asyncio import sleep

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_uow
from app.api.utils import get_operator, ok, require_local_token
from app.db.models import TaskModelBinding
from app.db.session import SessionLocal
from app.schemas import (
    ApiResponse,
    AttemptDetail,
    EvaluationResult,
    EvaluationTask,
    EvaluationTaskCreateRequest,
    PaginatedData,
    RetryFailedData,
    Statistics,
    TaskActionData,
    TaskStatus,
    TaskStatusData,
)
from app.services import EvaluationResultService, StatisticsService, TaskExecutionService, TaskService, UnitOfWork
from app.services.attack_strategies import StrategyConfigError, normalize_strategy
from app.workers.queue import (
    enqueue_failed_task_cases,
    enqueue_pending_task_cases,
    enqueue_task,
)

router = APIRouter()

TERMINAL_STATUSES = {"succeeded", "partially_failed", "failed", "cancelled"}


def _sse_event(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def _apply_raw_task_config(task, raw: dict) -> None:
    """把成员 3 需要的扩展配置合并进 task.config。

    ``EvaluationTaskCreateRequest`` 由成员 1 维护，暂未包含种子采样、攻击策略和
    PAIR 攻击模型字段；这里先读取原始 JSON 并写入 JSON 类型的 task.config，
    不新增数据库列，等成员 1 合并 schema 后再删除这段兼容逻辑。
    """
    if not isinstance(raw, dict):
        return
    config = dict(task.config or {})
    for key in (
        "seed_test_case_ids",
        "sample_size",
        "attack_strategy",
        "attacker_model_id",
        "attacker_system_prompt",
        "max_rounds",
    ):
        if key in raw and raw[key] is not None:
            config[key] = raw[key]

    if "seed_test_case_ids" in config:
        try:
            config["seed_test_case_ids"] = [int(item) for item in config["seed_test_case_ids"]]
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="seed_test_case_ids must be a list of integers") from exc

    if "sample_size" in config:
        try:
            config["sample_size"] = max(1, int(config["sample_size"]))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="sample_size must be an integer") from exc

    if "max_rounds" in config:
        try:
            config["max_rounds"] = max(1, min(int(config["max_rounds"]), 20))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="max_rounds must be an integer") from exc

    if "attacker_model_id" in config:
        try:
            config["attacker_model_id"] = int(config["attacker_model_id"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="attacker_model_id must be an integer") from exc

    raw_strategy = config.get("attack_strategy")
    if raw_strategy is not None:
        if not isinstance(raw_strategy, dict):
            raise HTTPException(status_code=422, detail="attack_strategy must be an object")
        try:
            strategy_type, strategy_code, strategy_config = normalize_strategy(
                raw_strategy.get("type") or raw_strategy.get("strategy_type"),
                raw_strategy.get("code") or raw_strategy.get("strategy_code"),
                raw_strategy.get("config") or raw_strategy.get("strategy_config"),
            )
        except StrategyConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        config["attack_strategy"] = {
            "type": strategy_type,
            "code": strategy_code,
            "config": strategy_config,
            "enabled": bool(raw_strategy.get("enabled", True)),
        }

    task.config = config


@router.post(
    "/evaluation-tasks",
    response_model=ApiResponse[EvaluationTask],
    operation_id="createEvaluationTask",
    tags=["评测任务"],
)
async def create_evaluation_task(
    payload: EvaluationTaskCreateRequest,
    request: Request,
    operator: str = Depends(get_operator),
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = TaskService(uow)
    try:
        task = service.create_task(payload, created_by=operator)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        raw_payload = await request.json()
    except Exception:
        raw_payload = {}
    _apply_raw_task_config(task, raw_payload)

    attacker_model_id = task.config.get("attacker_model_id")
    if attacker_model_id is not None:
        attacker_model = uow.models.get(int(attacker_model_id))
        if attacker_model is None or not attacker_model.enabled:
            raise HTTPException(status_code=422, detail="attacker model not found or disabled")
        existing_attacker = uow.task_model_bindings.list(
            page=1,
            page_size=1,
            task_id=task.id,
            model_id=int(attacker_model_id),
            role="attacker",
        )
        if not existing_attacker:
            uow.task_model_bindings.add(
                TaskModelBinding(
                    task_id=task.id,
                    model_id=int(attacker_model_id),
                    role="attacker",
                    model_params={},
                    enabled=True,
                )
            )

    uow.commit()
    enqueue_task(task.id)
    return ok(EvaluationTask.model_validate(task).model_dump())


@router.get(
    "/evaluation-tasks",
    response_model=ApiResponse[PaginatedData[EvaluationTask]],
    operation_id="listEvaluationTasks",
    tags=["评测任务"],
)
async def list_evaluation_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = TaskService(uow)
    items = service.list_tasks(page=page, page_size=page_size, status=status)
    total = uow.evaluation_tasks.count(status=status)
    return ok(PaginatedData[EvaluationTask](items=items, page=page, page_size=page_size, total=total).model_dump())


@router.get(
    "/evaluation-tasks/{task_id}/status",
    response_model=ApiResponse[TaskStatusData],
    operation_id="getEvaluationTaskStatus",
    tags=["评测任务"],
)
async def get_evaluation_task_status(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    snapshot = TaskService(uow).get_status_snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(TaskStatusData(**snapshot).model_dump(mode="json"))


@router.get(
    "/evaluation-tasks/{task_id}/results",
    response_model=ApiResponse[PaginatedData[EvaluationResult]],
    operation_id="listEvaluationResults",
    tags=["评测任务"],
)
async def list_evaluation_results(
    task_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str | None = None,
    needs_review: bool | None = None,
    model_id: int | None = None,
    attack_template_id: int | None = None,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = EvaluationResultService(uow)
    result = service.list_results(
        task_id=task_id,
        page=page,
        page_size=page_size,
        needs_review=needs_review,
        model_id=model_id,
        attack_template_id=attack_template_id,
    )
    return ok(result.model_dump())


@router.get(
    "/task-attempts/{attempt_id}",
    response_model=ApiResponse[AttemptDetail],
    operation_id="getTaskAttemptDetail",
    tags=["评测任务"],
)
async def get_task_attempt_detail(
    attempt_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    detail = EvaluationResultService(uow).get_attempt_detail(attempt_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="task attempt not found")
    return ok(detail.model_dump())


@router.post(
    "/evaluation-tasks/{task_id}/actions/start",
    response_model=ApiResponse[TaskActionData],
    operation_id="startEvaluationTask",
    tags=["评测任务"],
)
async def start_evaluation_task(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    task = uow.evaluation_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = TaskStatus.queued.value
    task.pause_requested = False
    task.cancel_requested = False
    uow.session.flush()
    uow.commit()
    enqueue_task(task.id)
    return ok(TaskActionData(task_id=task.id, status=task.status).model_dump())


@router.post(
    "/evaluation-tasks/{task_id}/actions/pause",
    response_model=ApiResponse[TaskActionData],
    operation_id="pauseEvaluationTask",
    tags=["评测任务"],
)
async def pause_evaluation_task(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    task = TaskService(uow).pause_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    uow.commit()
    return ok(TaskActionData(task_id=task.id, status=task.status, pause_requested=task.pause_requested).model_dump())


@router.post(
    "/evaluation-tasks/{task_id}/actions/resume",
    response_model=ApiResponse[TaskActionData],
    operation_id="resumeEvaluationTask",
    tags=["评测任务"],
)
async def resume_evaluation_task(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    task = TaskService(uow).resume_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    uow.commit()
    # 只派发 pending 用例，已成功的不重跑
    enqueue_pending_task_cases(task.id)
    return ok(TaskActionData(task_id=task.id, status=task.status, pause_requested=task.pause_requested).model_dump())


@router.post(
    "/evaluation-tasks/{task_id}/actions/cancel",
    response_model=ApiResponse[TaskActionData],
    operation_id="cancelEvaluationTask",
    tags=["评测任务"],
)
async def cancel_evaluation_task(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    service = TaskService(uow)
    task = service.cancel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ok(
        TaskActionData(
            task_id=task.id,
            status=task.status,
            cancel_requested=task.cancel_requested,
            pause_requested=task.pause_requested,
        ).model_dump()
    )


@router.post(
    "/evaluation-tasks/{task_id}/actions/retry-failed",
    response_model=ApiResponse[RetryFailedData],
    operation_id="retryFailedEvaluationCases",
    tags=["评测任务"],
)
async def retry_failed_evaluation_cases(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    task = uow.evaluation_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    retry_case_ids = TaskExecutionService(uow).prepare_retry_failed(task_id)
    uow.commit()
    if retry_case_ids:
        enqueue_failed_task_cases(task_id)
    return ok(
        RetryFailedData(
            task_id=task.id,
            retry_count=len(retry_case_ids),
            status=task.status,
        ).model_dump()
    )


@router.get(
    "/evaluation-tasks/{task_id}/statistics",
    response_model=ApiResponse[Statistics],
    operation_id="getEvaluationTaskStatistics",
    tags=["统计分析"],
)
async def get_evaluation_task_statistics(
    task_id: int,
    _: None = Depends(require_local_token),
    uow: UnitOfWork = Depends(get_uow),
) -> dict:
    stats = StatisticsService(uow).get_task_statistics(task_id, persist=True)
    if stats is None:
        raise HTTPException(status_code=404, detail="task not found")
    uow.commit()
    return ok(stats.model_dump(mode="json"))


@router.get(
    "/evaluation-tasks/{task_id}/events",
    operation_id="streamEvaluationTaskEvents",
    tags=["评测任务"],
    response_class=StreamingResponse,
)
async def stream_evaluation_task_events(
    task_id: int,
    request: Request,
    _: None = Depends(require_local_token),
) -> StreamingResponse:
    async def event_stream():
        previous_signature: str | None = None
        heartbeat = 0
        while True:
            if await request.is_disconnected():
                return
            with SessionLocal() as session:
                snapshot = TaskService(UnitOfWork(session)).get_status_snapshot(task_id)
            if snapshot is None:
                yield _sse_event("task_error", {"code": "TASK_NOT_FOUND", "message": "task not found"})
                return

            payload = TaskStatusData(**snapshot).model_dump(mode="json")
            signature = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            if signature != previous_signature:
                event_name = "done" if payload["status"] in TERMINAL_STATUSES else "progress"
                yield _sse_event(event_name, payload)
                previous_signature = signature

            if payload["status"] in TERMINAL_STATUSES:
                return

            heartbeat += 1
            if heartbeat >= 15:
                yield ": ping\n\n"
                heartbeat = 0
            await sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
