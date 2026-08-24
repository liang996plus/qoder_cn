"""数据处理模块的请求/响应 Pydantic 模型"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ── 通用数据载体 ─────────────────────────────────────────────

class DataFrameInput(BaseModel):
    """以 JSON 方式传入 DataFrame 数据"""
    columns: List[str] = Field(..., description="列名列表")
    data: List[List[Any]] = Field(..., description="二维数据，行优先")
    dtypes: Optional[Dict[str, str]] = Field(None, description="列类型提示，如 {'age': 'int64'}")


class DataFrameMeta(BaseModel):
    """DataFrame 元信息"""
    row_count: int
    column_count: int
    columns: List[str]
    dtypes: Dict[str, str]


class DataFrameOutput(BaseModel):
    """DataFrame 输出"""
    columns: List[str]
    data: List[List[Any]]
    meta: DataFrameMeta


# ── 数据解析 ─────────────────────────────────────────────────

class ParseResult(BaseModel):
    """文件解析结果"""
    columns: List[str]
    data: List[List[Any]]
    meta: DataFrameMeta
    file_type: str
    encoding: Optional[str] = None


# ── SQL 查询 ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """DuckDB SQL 查询请求"""
    dataframe: DataFrameInput
    sql: str = Field(..., description="SELECT 语句，表名为 df", examples=["SELECT * FROM df LIMIT 10"])
    table_name: str = Field("df", description="虚拟表名")


# ── 筛选 ─────────────────────────────────────────────────────

class FilterCondition(BaseModel):
    """单个筛选条件"""
    column: str
    operator: str = Field(..., description="运算符: eq, ne, gt, ge, lt, le, in, not_in, contains, startswith, endswith")
    value: Any


class FilterRequest(BaseModel):
    """数据筛选请求"""
    dataframe: DataFrameInput
    conditions: List[FilterCondition]
    logic: str = Field("and", description="条件组合方式: and / or")


# ── 聚合 ─────────────────────────────────────────────────────

class AggregateRequest(BaseModel):
    """聚合统计请求"""
    dataframe: DataFrameInput
    group_by: List[str] = Field(..., description="分组列")
    agg_columns: List[str] = Field(..., description="聚合目标列")
    agg_funcs: List[str] = Field(
        ...,
        description="聚合函数: sum, mean, count, min, max, median, std",
    )


# ── 透视 ─────────────────────────────────────────────────────

class PivotRequest(BaseModel):
    """透视表请求"""
    dataframe: DataFrameInput
    index: List[str] = Field(..., description="行索引列")
    columns: List[str] = Field(..., description="列展开列")
    values: List[str] = Field(..., description="值列")
    agg_func: str = Field("sum", description="聚合函数")


# ── 排序 ─────────────────────────────────────────────────────

class SortRequest(BaseModel):
    """排序请求"""
    dataframe: DataFrameInput
    sort_by: List[str] = Field(..., description="排序列")
    ascending: Union[bool, List[bool]] = Field(True, description="是否升序")


# ── 去重 ─────────────────────────────────────────────────────

class DedupRequest(BaseModel):
    """去重请求"""
    dataframe: DataFrameInput
    subset: Optional[List[str]] = Field(None, description="去重依据列，为空则全列去重")
    keep: str = Field("first", description="保留策略: first / last / false")


# ── 数据清洗 ─────────────────────────────────────────────────

class CleanOperation(BaseModel):
    """单个清洗操作"""
    operation: str = Field(
        ...,
        description="操作类型: fill_na, drop_na, cast_type, strip_text, replace_text, drop_outliers",
    )
    column: Optional[str] = Field(None, description="目标列，部分操作可为空表示全列")
    params: Optional[Dict[str, Any]] = Field(None, description="操作参数")


class CleanRequest(BaseModel):
    """数据清洗请求"""
    dataframe: DataFrameInput
    operations: List[CleanOperation]


# ── 统计分析 ──────────────────────────────────────────────────

class StatisticsType(str, Enum):
    DESCRIPTIVE = "descriptive"
    CORRELATION = "correlation"
    FREQUENCY = "frequency"


class StatisticsRequest(BaseModel):
    """统计分析请求"""
    dataframe: DataFrameInput
    stat_type: StatisticsType = Field(StatisticsType.DESCRIPTIVE, description="统计类型")
    columns: Optional[List[str]] = Field(None, description="目标列，为空则自动选择数值列")
    params: Optional[Dict[str, Any]] = Field(None, description="额外参数")
