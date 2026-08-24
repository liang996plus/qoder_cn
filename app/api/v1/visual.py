"""可视化路由 /api/v1/visual/*"""

from fastapi import APIRouter

from app.core.response import ApiResponse
from app.models.visual_models import ChartRequest, TableRequest
from app.services import visual_service
from app.services.data_service import input_to_df

router = APIRouter(prefix="/visual", tags=["可视化"])


@router.post("/chart", summary="生成图表", response_model=ApiResponse)
async def generate_chart(request: ChartRequest):
    """
    生成图表（柱状图/折线图/饼图/散点图/热力图/雷达图/面积图/直方图/箱线图）
    支持 PNG(base64) / SVG / HTML(plotly) 输出
    """
    df = input_to_df(request.dataframe)
    result = visual_service.generate_chart(df, request.config, request.output_format)
    return ApiResponse.success(data=result)


@router.post("/table", summary="渲染数据表格", response_model=ApiResponse)
async def render_table(request: TableRequest):
    """渲染格式化 HTML 表格，支持条件着色和排序"""
    df = input_to_df(request.dataframe)
    result = visual_service.render_table(df, request.config)
    return ApiResponse.success(data=result)
