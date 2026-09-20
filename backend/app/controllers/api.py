from fastapi import APIRouter

from app.controllers import actions, dashboard, experiments, identity, reports, safety, template_admin


api_router = APIRouter()
api_router.include_router(identity.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(safety.router)
api_router.include_router(actions.router)
api_router.include_router(experiments.router)
api_router.include_router(template_admin.router)
