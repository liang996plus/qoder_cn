"""流水线引擎 — 场景驱动的自动编排执行"""

from __future__ import annotations

import logging
import time
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.connectors import ConnectorRegistry
from app.core.errors import AppException
from app.core.response import ErrorCode
from app.core.scenario_loader import ScenarioConfig, PipelineStepConfig, DataSourceConfig
from app.models.pipeline_models import PipelineStepResult, OutputResult
from app.services import data_service, visual_service
from app.services.data_service import df_to_output, input_to_df
from app.models.data_models import (
    DataFrameInput,
    QueryRequest,
    FilterRequest,
    FilterCondition,
    AggregateRequest,
    PivotRequest,
    SortRequest,
    DedupRequest,
    CleanRequest,
    CleanOperation,
    StatisticsRequest,
)
from app.models.visual_models import ChartConfig, ChartType, OutputFormat, TableConfig

logger = logging.getLogger(__name__)


# ── PipelineContext ───────────────────────────────────────────

class PipelineContext:
    """流水线上下文，存储中间数据和执行状态"""

    def __init__(self, input_params: Dict[str, Any]):
        self._data: Dict[str, pd.DataFrame] = {}
        self._results: Dict[str, Any] = {}  # 非 DataFrame 的中间结果
        self.input_params = input_params
        self.step_results: List[PipelineStepResult] = []

    def set_df(self, name: str, df: pd.DataFrame) -> None:
        self._data[name] = df

    def get_df(self, name: str) -> pd.DataFrame:
        if name not in self._data:
            raise AppException(
                code=ErrorCode.PIPELINE_STEP_FAILED,
                message=f"PipelineContext 中不存在数据引用: '{name}'",
            )
        return self._data[name]

    def has(self, name: str) -> bool:
        return name in self._data or name in self._results

    def set_result(self, name: str, result: Any) -> None:
        self._results[name] = result

    def get_result(self, name: str) -> Any:
        return self._results.get(name)

    def get_input(self, key: str, default: Any = None) -> Any:
        return self.input_params.get(key, default)


# ── 参数解析 ──────────────────────────────────────────────────

_PARAM_REF_PATTERN = re.compile(r"\$input\.(\w+)")


def _resolve_param_mapping(
    config: Dict[str, Any], context: PipelineContext
) -> Dict[str, Any]:
    """
    解析参数映射，将 $input.xxx 替换为实际值。
    例如 {"file_content": "$input.file_content"} -> {"file_content": "base64..."}
    """
    resolved = {}
    for key, value in config.items():
        if key == "param_mapping":
            # param_mapping 子字典
            resolved.update(_resolve_param_mapping(value, context))
            continue
        if isinstance(value, str) and value.startswith("$input."):
            param_name = value[7:]  # 去掉 "$input."
            resolved[key] = context.get_input(param_name)
        elif isinstance(value, dict):
            resolved[key] = _resolve_param_mapping(value, context)
        else:
            resolved[key] = value
    return resolved


def _evaluate_condition(condition: str, context: PipelineContext) -> bool:
    """
    评估简单条件表达式，如：
    - "has:raw_data" — 检查 context 中是否存在 raw_data
    - "not_empty:raw_data" — 检查 raw_data 是否非空
    """
    condition = condition.strip()
    if condition.startswith("has:"):
        ref = condition[4:].strip()
        return context.has(ref)
    elif condition.startswith("not_empty:"):
        ref = condition[10:].strip()
        if not context.has(ref):
            return False
        try:
            df = context.get_df(ref)
            return not df.empty
        except Exception:
            return True
    return True


# ── Action 执行器 ─────────────────────────────────────────────

def _build_dataframe_input(df: pd.DataFrame) -> DataFrameInput:
    """将 DataFrame 构建为 DataFrameInput（供 service 层使用）"""
    columns = df.columns.tolist()
    data = df.values.tolist()
    return DataFrameInput(columns=columns, data=data)


def _execute_action(
    action: str,
    input_df: Optional[pd.DataFrame],
    params: Dict[str, Any],
    context: PipelineContext,
) -> Any:
    """根据 action 类型路由到对应的处理函数"""

    # ── 数据处理类 action ──
    if action == "query":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="query action 需要输入数据")
        sql = params.get("sql", "SELECT * FROM df")
        req = QueryRequest(
            dataframe=_build_dataframe_input(input_df),
            sql=sql,
            table_name=params.get("table_name", "df"),
        )
        return data_service.execute_query(req)

    elif action == "filter":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="filter action 需要输入数据")
        conditions = [
            FilterCondition(**c) for c in params.get("conditions", [])
        ]
        req = FilterRequest(
            dataframe=_build_dataframe_input(input_df),
            conditions=conditions,
            logic=params.get("logic", "and"),
        )
        return data_service.filter_data(req)

    elif action == "aggregate":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="aggregate action 需要输入数据")
        req = AggregateRequest(
            dataframe=_build_dataframe_input(input_df),
            group_by=params.get("group_by", []),
            agg_columns=params.get("agg_columns", []),
            agg_funcs=params.get("agg_funcs", ["sum"]),
        )
        return data_service.aggregate_data(req)

    elif action == "pivot":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="pivot action 需要输入数据")
        req = PivotRequest(
            dataframe=_build_dataframe_input(input_df),
            index=params.get("index", []),
            columns=params.get("columns", []),
            values=params.get("values", []),
            agg_func=params.get("agg_func", "sum"),
        )
        return data_service.pivot_data(req)

    elif action == "sort":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="sort action 需要输入数据")
        req = SortRequest(
            dataframe=_build_dataframe_input(input_df),
            sort_by=params.get("sort_by", []),
            ascending=params.get("ascending", True),
        )
        return data_service.sort_data(req)

    elif action == "dedup":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="dedup action 需要输入数据")
        req = DedupRequest(
            dataframe=_build_dataframe_input(input_df),
            subset=params.get("subset"),
            keep=params.get("keep", "first"),
        )
        return data_service.dedup_data(req)

    elif action == "clean":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="clean action 需要输入数据")
        operations = [
            CleanOperation(**op) for op in params.get("operations", [])
        ]
        req = CleanRequest(
            dataframe=_build_dataframe_input(input_df),
            operations=operations,
        )
        return data_service.clean_data(req)

    elif action == "statistics":
        if input_df is None:
            raise AppException(code=ErrorCode.PIPELINE_STEP_FAILED, message="statistics action 需要输入数据")
        req = StatisticsRequest(
            dataframe=_build_dataframe_input(input_df),
            stat_type=params.get("stat_type", "descriptive"),
            columns=params.get("columns"),
            params=params.get("extra_params"),
        )
        return data_service.compute_statistics(req)

    else:
        raise AppException(
            code=ErrorCode.PIPELINE_STEP_FAILED,
            message=f"不支持的 action: '{action}'",
        )


def _result_to_df(result: Any) -> pd.DataFrame:
    """将 action 执行结果（dict）转回 DataFrame"""
    if isinstance(result, dict) and "columns" in result and "data" in result:
        return pd.DataFrame(result["data"], columns=result["columns"])
    raise AppException(
        code=ErrorCode.PIPELINE_STEP_FAILED,
        message="无法将步骤结果转为 DataFrame",
    )


# ── PipelineEngine ────────────────────────────────────────────

class PipelineEngine:
    """流水线引擎"""

    async def run(
        self,
        scenario: ScenarioConfig,
        input_params: Dict[str, Any],
    ) -> tuple[List[PipelineStepResult], List[OutputResult], float]:
        """
        执行完整的 Pipeline 流程

        Returns:
            (step_results, outputs, total_duration_ms)
        """
        total_start = time.perf_counter()
        context = PipelineContext(input_params)

        # ── 1. 加载数据源 ──
        for ds in scenario.data_sources:
            connector = ConnectorRegistry.get(ds.connector)
            resolved_config = _resolve_param_mapping(ds.config, context)
            df = await connector.fetch(resolved_config)
            context.set_df(ds.name, df)
            logger.info("数据源 '%s' 加载完成 (%d 行)", ds.name, len(df))

        # ── 2. 执行 Pipeline 步骤 ──
        for step in scenario.pipeline:
            step_start = time.perf_counter()

            try:
                # 条件检查
                if step.condition and not _evaluate_condition(step.condition, context):
                    duration = (time.perf_counter() - step_start) * 1000
                    context.step_results.append(PipelineStepResult(
                        step_name=step.name,
                        status="skipped",
                        duration_ms=round(duration, 2),
                        message="条件不满足，已跳过",
                    ))
                    continue

                # 获取输入数据
                input_df = None
                if step.input and context.has(step.input):
                    input_df = context.get_df(step.input)

                # 解析参数中的 $input 引用
                resolved_params = _resolve_param_mapping(step.params, context)

                # 执行 action
                result = _execute_action(step.action, input_df, resolved_params, context)

                # 存储结果
                if step.output:
                    if isinstance(result, dict) and "columns" in result and "data" in result:
                        result_df = _result_to_df(result)
                        context.set_df(step.output, result_df)
                    context.set_result(step.output, result)

                duration = (time.perf_counter() - step_start) * 1000
                context.step_results.append(PipelineStepResult(
                    step_name=step.name,
                    status="success",
                    duration_ms=round(duration, 2),
                    message="执行成功",
                ))
                logger.info("步骤 '%s' 执行成功 (%.1fms)", step.name, duration)

            except AppException as e:
                duration = (time.perf_counter() - step_start) * 1000
                context.step_results.append(PipelineStepResult(
                    step_name=step.name,
                    status="failed",
                    duration_ms=round(duration, 2),
                    message=str(e.message),
                ))

                if step.on_error == "skip":
                    logger.warning("步骤 '%s' 失败，已跳过: %s", step.name, e.message)
                    continue
                else:
                    # abort
                    logger.error("步骤 '%s' 失败，终止流程: %s", step.name, e.message)
                    total_duration = (time.perf_counter() - total_start) * 1000
                    return context.step_results, [], round(total_duration, 2)

            except Exception as e:
                duration = (time.perf_counter() - step_start) * 1000
                context.step_results.append(PipelineStepResult(
                    step_name=step.name,
                    status="failed",
                    duration_ms=round(duration, 2),
                    message=f"未预期异常: {type(e).__name__}: {str(e)}",
                ))

                if step.on_error == "skip":
                    logger.warning("步骤 '%s' 未预期异常，已跳过", step.name)
                    continue
                else:
                    total_duration = (time.perf_counter() - total_start) * 1000
                    return context.step_results, [], round(total_duration, 2)

        # ── 3. 组装输出 ──
        from app.core.output_assembler import assemble_outputs
        outputs = assemble_outputs(scenario.outputs, context)

        total_duration = (time.perf_counter() - total_start) * 1000
        return context.step_results, outputs, round(total_duration, 2)
