"""健康检查路由 — 无需认证"""

from fastapi import APIRouter

from app.core.response import ApiResponse

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="健康检查", response_model=ApiResponse)
async def health_check():
    return ApiResponse.success(data={"status": "healthy"})
