from fastapi import APIRouter

from app.controllers import actions, dashboard, experiments, reports


api_router = APIRouter()
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(actions.router)
api_router.include_router(experiments.router)

