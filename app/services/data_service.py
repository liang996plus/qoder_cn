"""数据处理业务逻辑"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional

import chardet
import duckdb
import numpy as np
import pandas as pd

from app.core.errors import AppException
from app.core.response import ErrorCode
from app.models.data_models import (
    AggregateRequest,
    CleanOperation,
    CleanRequest,
    DataFrameInput,
    DataFrameMeta,
    DedupRequest,
    FilterCondition,
    FilterRequest,
    PivotRequest,
    QueryRequest,
    SortRequest,
    StatisticsRequest,
    StatisticsType,
)


# ── 辅助函数 ──────────────────────────────────────────────────

def input_to_df(dataframe: DataFrameInput) -> pd.DataFrame:
    """将 DataFrameInput 转换为 pandas DataFrame"""
    df = pd.DataFrame(dataframe.data, columns=dataframe.columns)
    if dataframe.dtypes:
        for col, dtype in dataframe.dtypes.items():
            if col in df.columns:
                try:
                    df[col] = df[col].astype(dtype)
                except (ValueError, TypeError):
                    pass  # 类型转换失败保持原样
    return df


def df_to_output(df: pd.DataFrame) -> Dict[str, Any]:
    """将 DataFrame 转换为可序列化的输出字典"""
    # 处理 NaN/Inf 值
    df_clean = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    columns = df_clean.columns.tolist()
    data = df_clean.values.tolist()
    # 将 numpy 类型转为 Python 原生类型
    data = [
        [
            item.item() if isinstance(item, (np.integer, np.floating)) else item
            for item in row
        ]
        for row in data
    ]
    meta = DataFrameMeta(
        row_count=len(df_clean),
        column_count=len(columns),
        columns=columns,
        dtypes={col: str(df[col].dtype) for col in columns},
    )
    return {
        "columns": columns,
        "data": data,
        "meta": meta.model_dump(),
    }


# ── 数据解析 ──────────────────────────────────────────────────

def parse_file(file_content: bytes, filename: str) -> Dict[str, Any]:
    """解析上传的文件为 DataFrame"""
    lower_name = filename.lower()

    # 自动编码检测
    encoding = None
    if lower_name.endswith(".csv") or lower_name.endswith(".json"):
        detected = chardet.detect(file_content)
        encoding = detected.get("encoding", "utf-8") or "utf-8"

    try:
        if lower_name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
            file_type = "csv"
        elif lower_name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_content))
            file_type = "excel"
            encoding = None
        elif lower_name.endswith(".json"):
            df = pd.read_json(io.BytesIO(file_content), encoding=encoding)
            file_type = "json"
        else:
            raise AppException(
                code=ErrorCode.FILE_PARSE_ERROR,
                message=f"不支持的文件格式: {filename}",
            )
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            code=ErrorCode.FILE_PARSE_ERROR,
            message=f"文件解析失败: {str(e)}",
        )

    if df.empty:
        raise AppException(code=ErrorCode.DATA_EMPTY, message="文件内容为空")

    result = df_to_output(df)
    result["file_type"] = file_type
    result["encoding"] = encoding
    return result


# ── SQL 查询 ──────────────────────────────────────────────────

_SQL_DANGEROUS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE|COPY|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)


def execute_query(request: QueryRequest) -> Dict[str, Any]:
    """执行 DuckDB SQL 查询"""
    # SQL 注入防护：只允许 SELECT
    if _SQL_DANGEROUS.search(request.sql):
        raise AppException(
            code=ErrorCode.SQL_EXECUTION_ERROR,
            message="SQL 安全限制：仅允许 SELECT 查询",
        )

    sql_upper = request.sql.strip().lstrip('\ufeff"\'').strip().upper()
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        raise AppException(
            code=ErrorCode.SQL_EXECUTION_ERROR,
            message="SQL 必须以 SELECT 或 WITH 开头",
        )

    df = input_to_df(request.dataframe)
    table_name = request.table_name or "df"

    try:
        con = duckdb.connect(":memory:")
        con.register(table_name, df)
        result_df = con.execute(request.sql).fetchdf()
        con.close()
    except duckdb.Error as e:
        raise AppException(
            code=ErrorCode.SQL_EXECUTION_ERROR,
            message=f"SQL 执行错误: {str(e)}",
        )

    return df_to_output(result_df)


# ── 筛选 ──────────────────────────────────────────────────────

_OPERATOR_MAP = {
    "eq": lambda s, v: s == v,
    "ne": lambda s, v: s != v,
    "gt": lambda s, v: s > v,
    "ge": lambda s, v: s >= v,
    "lt": lambda s, v: s < v,
    "le": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v),
    "not_in": lambda s, v: ~s.isin(v),
    "contains": lambda s, v: s.astype(str).str.contains(str(v), na=False),
    "startswith": lambda s, v: s.astype(str).str.startswith(str(v)),
    "endswith": lambda s, v: s.astype(str).str.endswith(str(v)),
}


def filter_data(request: FilterRequest) -> Dict[str, Any]:
    """按条件筛选数据"""
    df = input_to_df(request.dataframe)

    if not request.conditions:
        return df_to_output(df)

    masks = []
    for cond in request.conditions:
        if cond.column not in df.columns:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message=f"列 '{cond.column}' 不存在",
            )
        op_func = _OPERATOR_MAP.get(cond.operator)
        if op_func is None:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message=f"不支持的运算符: {cond.operator}",
            )
        masks.append(op_func(df[cond.column], cond.value))

    if request.logic == "or":
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m
    else:
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m

    result_df = df[combined].reset_index(drop=True)
    return df_to_output(result_df)


# ── 聚合 ──────────────────────────────────────────────────────

_VALID_AGG_FUNCS = {"sum", "mean", "count", "min", "max", "median", "std", "var"}


def aggregate_data(request: AggregateRequest) -> Dict[str, Any]:
    """聚合统计"""
    df = input_to_df(request.dataframe)

    for func in request.agg_funcs:
        if func not in _VALID_AGG_FUNCS:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message=f"不支持的聚合函数: {func}",
            )

    agg_dict = {col: request.agg_funcs for col in request.agg_columns}
    try:
        result_df = df.groupby(request.group_by).agg(agg_dict)
        # 扁平化 MultiIndex 列名
        result_df.columns = [
            f"{col}_{func}" for col, func in result_df.columns
        ]
        result_df = result_df.reset_index()
    except Exception as e:
        raise AppException(
            code=ErrorCode.DATA_TYPE_ERROR,
            message=f"聚合执行失败: {str(e)}",
        )

    return df_to_output(result_df)


# ── 透视 ──────────────────────────────────────────────────────

def pivot_data(request: PivotRequest) -> Dict[str, Any]:
    """透视表"""
    df = input_to_df(request.dataframe)
    try:
        result_df = pd.pivot_table(
            df,
            index=request.index,
            columns=request.columns,
            values=request.values,
            aggfunc=request.agg_func,
        )
        result_df = result_df.reset_index()
        # 扁平化列名
        if isinstance(result_df.columns, pd.MultiIndex):
            result_df.columns = [
                "_".join(str(c) for c in col).strip("_")
                for col in result_df.columns
            ]
    except Exception as e:
        raise AppException(
            code=ErrorCode.DATA_TYPE_ERROR,
            message=f"透视表生成失败: {str(e)}",
        )

    return df_to_output(result_df)


# ── 排序 ──────────────────────────────────────────────────────

def sort_data(request: SortRequest) -> Dict[str, Any]:
    """排序"""
    df = input_to_df(request.dataframe)
    result_df = df.sort_values(
        by=request.sort_by,
        ascending=request.ascending,
    ).reset_index(drop=True)
    return df_to_output(result_df)


# ── 去重 ──────────────────────────────────────────────────────

def dedup_data(request: DedupRequest) -> Dict[str, Any]:
    """去重"""
    df = input_to_df(request.dataframe)
    subset = request.subset if request.subset else None
    keep = request.keep if request.keep in ("first", "last", False) else "first"
    result_df = df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)
    return df_to_output(result_df)


# ── 数据清洗 ──────────────────────────────────────────────────

def clean_data(request: CleanRequest) -> Dict[str, Any]:
    """数据清洗"""
    df = input_to_df(request.dataframe)

    for op in request.operations:
        df = _apply_clean_operation(df, op)

    return df_to_output(df)


def _apply_clean_operation(df: pd.DataFrame, op: CleanOperation) -> pd.DataFrame:
    """应用单个清洗操作"""
    params = op.params or {}

    if op.operation == "fill_na":
        fill_value = params.get("value", 0)
        if op.column:
            df[op.column] = df[op.column].fillna(fill_value)
        else:
            df = df.fillna(fill_value)

    elif op.operation == "drop_na":
        subset = [op.column] if op.column else None
        how = params.get("how", "any")
        df = df.dropna(subset=subset, how=how).reset_index(drop=True)

    elif op.operation == "cast_type":
        if not op.column:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message="cast_type 操作必须指定 column",
            )
        target_type = params.get("type", "str")
        try:
            if target_type in ("int", "int64"):
                df[op.column] = pd.to_numeric(df[op.column], errors="coerce").astype("Int64")
            elif target_type in ("float", "float64"):
                df[op.column] = pd.to_numeric(df[op.column], errors="coerce")
            elif target_type in ("str", "string"):
                df[op.column] = df[op.column].astype(str)
            elif target_type == "datetime":
                fmt = params.get("format")
                df[op.column] = pd.to_datetime(df[op.column], format=fmt, errors="coerce")
            elif target_type == "bool":
                df[op.column] = df[op.column].astype(bool)
            else:
                df[op.column] = df[op.column].astype(target_type)
        except Exception as e:
            raise AppException(
                code=ErrorCode.DATA_TYPE_ERROR,
                message=f"类型转换失败 ({op.column} -> {target_type}): {str(e)}",
            )

    elif op.operation == "strip_text":
        if op.column:
            df[op.column] = df[op.column].astype(str).str.strip()
        else:
            for col in df.select_dtypes(include=["object", "string"]).columns:
                df[col] = df[col].astype(str).str.strip()

    elif op.operation == "replace_text":
        if not op.column:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message="replace_text 操作必须指定 column",
            )
        pattern = params.get("pattern", "")
        replacement = params.get("replacement", "")
        regex = params.get("regex", False)
        df[op.column] = df[op.column].astype(str).str.replace(
            pattern, replacement, regex=regex
        )

    elif op.operation == "drop_outliers":
        if not op.column:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message="drop_outliers 操作必须指定 column",
            )
        col_data = pd.to_numeric(df[op.column], errors="coerce")
        q1 = col_data.quantile(0.25)
        q3 = col_data.quantile(0.75)
        iqr = q3 - q1
        factor = params.get("factor", 1.5)
        lower = q1 - factor * iqr
        upper = q3 + factor * iqr
        mask = (col_data >= lower) & (col_data <= upper)
        df = df[mask].reset_index(drop=True)

    else:
        raise AppException(
            code=ErrorCode.PARAM_VALIDATION_ERROR,
            message=f"不支持的清洗操作: {op.operation}",
        )

    return df


# ── 统计分析 ──────────────────────────────────────────────────

def compute_statistics(request: StatisticsRequest) -> Dict[str, Any]:
    """统计分析"""
    df = input_to_df(request.dataframe)

    # 确定目标列
    if request.columns:
        target_cols = request.columns
    else:
        target_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not target_cols:
        raise AppException(code=ErrorCode.DATA_EMPTY, message="没有可用于统计的数值列")

    if request.stat_type == StatisticsType.DESCRIPTIVE:
        stats_df = df[target_cols].describe()
        return df_to_output(stats_df.reset_index().rename(columns={"index": "stat"}))

    elif request.stat_type == StatisticsType.CORRELATION:
        if len(target_cols) < 2:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message="相关性分析至少需要 2 个数值列",
            )
        corr_df = df[target_cols].corr()
        return df_to_output(corr_df.reset_index().rename(columns={"index": "column"}))

    elif request.stat_type == StatisticsType.FREQUENCY:
        if not target_cols:
            raise AppException(
                code=ErrorCode.PARAM_VALIDATION_ERROR,
                message="频率分布至少需要指定 1 列",
            )
        col = target_cols[0]
        bins = (request.params or {}).get("bins", 10)
        if pd.api.types.is_numeric_dtype(df[col]):
            freq = pd.cut(df[col], bins=bins).value_counts().sort_index()
        else:
            freq = df[col].value_counts()
        result_df = freq.reset_index()
        result_df.columns = [col, "count"]
        result_df["percentage"] = (result_df["count"] / result_df["count"].sum() * 100).round(2)
        return df_to_output(result_df)

    raise AppException(
        code=ErrorCode.PARAM_VALIDATION_ERROR,
        message=f"不支持的统计类型: {request.stat_type}",
    )
