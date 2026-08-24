"""可视化模块的请求/响应 Pydantic 模型"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.models.data_models import DataFrameInput


# ── 图表类型枚举 ──────────────────────────────────────────────

class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    RADAR = "radar"
    AREA = "area"
    HISTOGRAM = "histogram"
    BOX = "box"


class OutputFormat(str, Enum):
    PNG = "png"
    SVG = "svg"
    HTML = "html"


# ── 图表配置 ─────────────────────────────────────────────────

class AxisConfig(BaseModel):
    """坐标轴配置"""
    label: Optional[str] = None
    tick_rotation: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class ChartConfig(BaseModel):
    """图表配置"""
    chart_type: ChartType
    x: Optional[str] = Field(None, description="X 轴列名")
    y: Optional[Union[str, List[str]]] = Field(None, description="Y 轴列名，可为列表（多系列）")
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    colors: Optional[List[str]] = None
    width: int = Field(800, ge=200, le=2000)
    height: int = Field(600, ge=200, le=2000)
    x_axis: Optional[AxisConfig] = None
    y_axis: Optional[AxisConfig] = None
    extra: Optional[Dict[str, Any]] = Field(None, description="额外配置参数")


# ── 图表请求/响应 ─────────────────────────────────────────────

class ChartRequest(BaseModel):
    """图表生成请求"""
    dataframe: DataFrameInput
    config: ChartConfig
    output_format: OutputFormat = OutputFormat.PNG


class ChartResponse(BaseModel):
    """图表生成响应"""
    image_base64: Optional[str] = Field(None, description="PNG/SVG base64 编码")
    html_content: Optional[str] = Field(None, description="HTML 格式输出")
    filename: Optional[str] = Field(None, description="临时文件名，可通过下载接口获取")
    output_format: str


# ── 表格渲染 ─────────────────────────────────────────────────

class ConditionalStyle(BaseModel):
    """条件样式"""
    column: str
    condition: str = Field(..., description="条件表达式，如 '> 100', '== A'")
    style: Dict[str, str] = Field(..., description="CSS 样式，如 {'background-color': 'red'}")


class TableConfig(BaseModel):
    """表格渲染配置"""
    title: Optional[str] = None
    sort_by: Optional[str] = None
    sort_ascending: bool = True
    max_rows: Optional[int] = Field(None, description="最大显示行数")
    conditional_styles: Optional[List[ConditionalStyle]] = None
    column_widths: Optional[Dict[str, str]] = None
    show_index: bool = False


class TableRequest(BaseModel):
    """表格渲染请求"""
    dataframe: DataFrameInput
    config: Optional[TableConfig] = None


class TableResponse(BaseModel):
    """表格渲染响应"""
    html: str
    row_count: int
    column_count: int
