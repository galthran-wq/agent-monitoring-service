from fastapi import APIRouter

from src.api.endpoints import health, report

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(report.router, tags=["report"])
