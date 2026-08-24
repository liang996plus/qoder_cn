"""报表生成 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.file_manager import save_file
from app.core.response import ApiResponse
from app.models.report_models import ReportFileResult, TermTargetReviewRequest
from app.services import report_service

router = APIRouter(prefix="/report", tags=["报表生成"])


@router.post(
    "/term-target-review",
    summary="生成分期限目标检视 Excel 报表",
    response_model=None,
)
async def generate_term_target_review(request: TermTargetReviewRequest, raw_request: Request):
    """接收结构化数据，填充模板生成 Excel 并返回下载链接"""
    xlsx_bytes = report_service.generate_term_target_review(request)

    filename = save_file(content=xlsx_bytes, suffix=".xlsx", prefix="report_term_target_review_")

    base_url = str(raw_request.base_url).rstrip("/")
    result = ReportFileResult(
        filename=filename,
        format="xlsx",
        download_url=f"{base_url}/api/v1/file/download/{filename}",
        row_count=len(request.rows),
        column_count=6,
    )
    return ApiResponse.success(data=result.model_dump())
