"""v1 路由汇总"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.data import router as data_router
from app.api.v1.visual import router as visual_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.report import router as report_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(data_router)
router.include_router(visual_router)
router.include_router(pipeline_router)
router.include_router(report_router)
