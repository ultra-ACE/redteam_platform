from fastapi import APIRouter

from app.api.v1.routes import attack, benchmark, file, judge, model, report, report_templates, review, risk, system, tasks

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(benchmark.router)
api_router.include_router(risk.router)
api_router.include_router(model.router)
api_router.include_router(attack.router)
api_router.include_router(tasks.router)
api_router.include_router(judge.router)
api_router.include_router(review.router)
api_router.include_router(report.router)
api_router.include_router(report_templates.router)
api_router.include_router(file.router)
