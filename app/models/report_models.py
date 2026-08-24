"""分期限目标检视报表 — 请求/响应模型"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class TermTargetRow(BaseModel):
    """单行数据"""

    product_type: str = Field(..., max_length=50, description="产品类型")
    term_category: Optional[str] = Field(None, max_length=100, description="期限分类，总计行可为空")
    daily_scale: float = Field(..., description="当日规模，保留两位小数")
    vs_last_month: float = Field(..., description="较上月末变化，保留两位小数")
    sales_analysis: str = Field(..., max_length=5000, description="销量分析文本")


class TermTargetReviewRequest(BaseModel):
    """分期限目标检视报表请求"""

    current_date: date = Field(..., description="当前日期，ISO 格式 YYYY-MM-DD")
    rows: List[TermTargetRow] = Field(..., min_length=1, max_length=5, description="数据行数组（1-5行）")


class ReportFileResult(BaseModel):
    """报表文件生成结果"""

    filename: str = Field(..., description="生成的文件名")
    format: str = Field("xlsx", description="文件格式")
    download_url: str = Field(..., description="文件下载路径")
    row_count: int = Field(..., description="数据行数（不含表头和合计行）")
    column_count: int = Field(6, description="列数（固定6）")
