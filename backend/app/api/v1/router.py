from fastapi import APIRouter

from app.api.v1.routes import attack, benchmark, file, health, judge, model, report, review, tasks

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(benchmark.router)
api_router.include_router(model.router)
api_router.include_router(attack.router)
api_router.include_router(tasks.router)
api_router.include_router(judge.router)
api_router.include_router(review.router)
api_router.include_router(report.router)
api_router.include_router(file.router)
