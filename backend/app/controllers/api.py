from fastapi import APIRouter

from app.controllers import (
    actions,
    care_plans,
    catalog,
    content_admin,
    dashboard,
    experiments,
    identity,
    metrics,
    reports,
    safety,
    safety_admin,
    template_admin,
)


api_router = APIRouter()
api_router.include_router(identity.router)
api_router.include_router(catalog.router)
api_router.include_router(care_plans.router)
api_router.include_router(content_admin.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(metrics.router)
api_router.include_router(safety.router)
api_router.include_router(safety_admin.router)
api_router.include_router(actions.router)
api_router.include_router(experiments.router)
api_router.include_router(template_admin.router)
