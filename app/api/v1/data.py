"""数据处理路由 /api/v1/data/*"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.core import db as db_manager
from app.core.errors import AppException
from app.core.response import ApiResponse, ErrorCode
from app.models.data_models import (
    AggregateRequest,
    CleanRequest,
    DataFrameInput,
    DedupRequest,
    FilterRequest,
    PivotRequest,
    QueryRequest,
    SortRequest,
    StatisticsRequest,
)
from app.services import data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["数据处理"])


# ── 数据集入库相关模型 ─────────────────────────────────────────────

class DatasetQueryRequest(BaseModel):
    """数据集 SQL 查询请求"""
    sql: str = Field(..., description="SELECT 语句，表名使用 ingest 返回的 table_name")


# ── 数据集入库接口 ─────────────────────────────────────────────────

@router.post("/ingest", summary="接收数据文件并入库（SQLite）")
async def ingest_file(
    file: UploadFile = File(..., description="CSV/Excel/JSON 数据文件"),
    table_name: Optional[str] = Form(None, description="自定义表名，append 模式下必填"),
    description: Optional[str] = Form("", description="数据集描述"),
    mode: Optional[str] = Form("create", description="入库模式: create（新建）或 append（追加）"),
):
    """
    接收上游系统下发的数据文件，解析后持久化到 SQLite。

    - **create**（默认）：新建表，表名已存在时报错
    - **append**：追加行到已有表，必须指定 table_name，列名不匹配或表不存在时报错
    """
    if mode not in ("create", "append"):
        raise AppException(
            code=ErrorCode.DATASET_ERROR,
            message=f"不支持的入库模式: {mode}，可选值: create / append",
        )

    content = await file.read()
    filename = file.filename or "unknown"

    try:
        result = data_service.parse_file(content, filename)
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            code=ErrorCode.FILE_PARSE_ERROR,
            message=f"文件解析失败: {str(e)}",
        )

    import pandas as pd

    df = pd.DataFrame(result["data"], columns=result["columns"])
    dataset = await db_manager.ingest_dataframe(
        df=df,
        table_name=table_name,
        filename=filename,
        description=description or "",
        file_type=result.get("file_type", ""),
        encoding=result.get("encoding"),
        mode=mode or "create",
    )
    return ApiResponse.success(data=dataset)


@router.get("/datasets", summary="列出所有已入库数据集")
async def list_datasets():
    """返回 SQLite 中所有已入库的数据集元信息列表"""
    datasets = await db_manager.list_datasets()
    return ApiResponse.success(data=datasets)


@router.get("/datasets/{dataset_id}", summary="获取数据集详情")
async def get_dataset(dataset_id: str, preview: int = 0):
    """
    获取单个数据集的元信息。
    preview=N 时额外返回前 N 行数据预览。
    """
    dataset = await db_manager.get_dataset(dataset_id, preview=preview)
    if dataset is None:
        raise AppException(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"数据集不存在: {dataset_id}",
        )
    return ApiResponse.success(data=dataset)


@router.post("/datasets/{dataset_id}/query", summary="SQL 查询已入库数据")
async def query_dataset(dataset_id: str, request: DatasetQueryRequest):
    """
    对 SQLite 库中的数据执行 SELECT 查询。
    表名请使用 ingest 接口返回的 table_name 字段。
    安全限制：仅允许 SELECT / WITH 开头的语句。
    """
    dataset = await db_manager.get_dataset(dataset_id)
    if dataset is None:
        raise AppException(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"数据集不存在: {dataset_id}",
        )
    result = await db_manager.query_dataset(request.sql)
    return ApiResponse.success(data=result)


@router.delete("/datasets/{dataset_id}", summary="删除已入库数据集")
async def delete_dataset(dataset_id: str):
    """删除数据集及其对应的 SQLite 表"""
    deleted = await db_manager.delete_dataset(dataset_id)
    if not deleted:
        raise AppException(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"数据集不存在: {dataset_id}",
        )
    return ApiResponse.success(data={"deleted": True, "id": dataset_id})


# ── 单步数据处理接口 ─────────────────────────────────────────────

@router.post("/parse", summary="上传文件解析为 DataFrame")
async def parse_file(file: UploadFile = File(...)):
    """支持 CSV/Excel/JSON 格式，自动编码检测"""
    content = await file.read()
    result = data_service.parse_file(content, file.filename or "unknown")
    return ApiResponse.success(data=result)


@router.post("/query", summary="DuckDB SQL 查询", response_model=ApiResponse)
async def query_data(request: QueryRequest):
    """接收 DataFrame + SELECT 语句，返回查询结果"""
    result = data_service.execute_query(request)
    return ApiResponse.success(data=result)


@router.post("/filter", summary="数据筛选", response_model=ApiResponse)
async def filter_data(request: FilterRequest):
    """按条件筛选数据"""
    result = data_service.filter_data(request)
    return ApiResponse.success(data=result)


@router.post("/aggregate", summary="聚合统计", response_model=ApiResponse)
async def aggregate_data(request: AggregateRequest):
    """分组聚合（groupby + sum/mean/count 等）"""
    result = data_service.aggregate_data(request)
    return ApiResponse.success(data=result)


@router.post("/pivot", summary="透视表", response_model=ApiResponse)
async def pivot_data(request: PivotRequest):
    """生成透视表"""
    result = data_service.pivot_data(request)
    return ApiResponse.success(data=result)


@router.post("/sort", summary="排序", response_model=ApiResponse)
async def sort_data(request: SortRequest):
    """按指定列排序"""
    result = data_service.sort_data(request)
    return ApiResponse.success(data=result)


@router.post("/dedup", summary="去重", response_model=ApiResponse)
async def dedup_data(request: DedupRequest):
    """数据去重"""
    result = data_service.dedup_data(request)
    return ApiResponse.success(data=result)


@router.post("/clean", summary="数据清洗", response_model=ApiResponse)
async def clean_data(request: CleanRequest):
    """空值处理、类型转换、文本清洗、异常值过滤"""
    result = data_service.clean_data(request)
    return ApiResponse.success(data=result)


@router.post("/statistics", summary="统计分析", response_model=ApiResponse)
async def compute_statistics(request: StatisticsRequest):
    """描述性统计、相关性矩阵、频率分布"""
    result = data_service.compute_statistics(request)
    return ApiResponse.success(data=result)
