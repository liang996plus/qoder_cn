"""输出组装器 — 将 PipelineContext 中的结果渲染为最终输出"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.core.file_manager import save_file
from app.core.scenario_loader import OutputConfig
from app.models.pipeline_models import OutputResult
from app.services.data_service import df_to_output

logger = logging.getLogger(__name__)


def assemble_outputs(
    output_configs: List[OutputConfig],
    context: Any,  # PipelineContext (避免循环导入)
) -> List[OutputResult]:
    """根据输出定义组装最终结果"""
    results: List[OutputResult] = []

    for output_cfg in output_configs:
        try:
            result = _assemble_single(output_cfg, context)
            results.append(result)
        except Exception as e:
            logger.warning("输出 '%s' 组装失败: %s", output_cfg.name, str(e))
            results.append(OutputResult(
                name=output_cfg.name,
                type=output_cfg.type,
                data={"error": str(e)},
            ))

    return results


def _assemble_single(
    output_cfg: OutputConfig,
    context: Any,
) -> OutputResult:
    """组装单个输出"""
    source_data = None
    if context.has(output_cfg.source):
        source_data = context.get_df(output_cfg.source)

    if output_cfg.type == "table":
        return _assemble_table(output_cfg, source_data)
    elif output_cfg.type == "chart":
        return _assemble_chart(output_cfg, source_data)
    elif output_cfg.type == "file":
        return _assemble_file(output_cfg, source_data)
    elif output_cfg.type == "summary":
        return _assemble_summary(output_cfg, source_data)
    else:
        raise ValueError(f"不支持的输出类型: {output_cfg.type}")


def _assemble_table(output_cfg: OutputConfig, df: pd.DataFrame) -> OutputResult:
    """表格输出 — 返回格式化数据"""
    from app.services import visual_service
    from app.models.visual_models import TableConfig

    config = output_cfg.config or {}
    table_config = None
    if config:
        table_config = TableConfig(**{
            k: v for k, v in config.items()
            if k in TableConfig.model_fields
        })

    result = visual_service.render_table(df, table_config)
    return OutputResult(
        name=output_cfg.name,
        type="table",
        data=result,
    )


def _assemble_chart(output_cfg: OutputConfig, df: pd.DataFrame) -> OutputResult:
    """图表输出 — 生成图表"""
    from app.services import visual_service
    from app.models.visual_models import ChartConfig, OutputFormat

    config = output_cfg.config or {}
    chart_type_str = config.get("chart_type", "bar")
    try:
        chart_type = ChartType(chart_type_str)
    except ValueError:
        chart_type = ChartType.BAR

    chart_config = ChartConfig(
        chart_type=chart_type,
        x=config.get("x"),
        y=config.get("y"),
        title=config.get("title"),
        xlabel=config.get("xlabel"),
        ylabel=config.get("ylabel"),
        colors=config.get("colors"),
        width=config.get("width", 800),
        height=config.get("height", 600),
    )

    output_format_str = config.get("output_format", "png")
    output_format = OutputFormat(output_format_str) if output_format_str in ("png", "svg", "html") else OutputFormat.PNG

    result = visual_service.generate_chart(df, chart_config, output_format)
    return OutputResult(
        name=output_cfg.name,
        type="chart",
        data=result,
    )


def _assemble_file(output_cfg: OutputConfig, df: pd.DataFrame) -> OutputResult:
    """文件输出 — 导出为文件并返回下载信息"""
    config = output_cfg.config or {}
    fmt = config.get("format", "csv")

    if fmt == "csv":
        content = df.to_csv(index=False).encode("utf-8")
        suffix = ".csv"
    elif fmt in ("xlsx", "excel"):
        import io
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        content = buf.getvalue()
        suffix = ".xlsx"
    elif fmt == "json":
        content = df.to_json(orient="records", force_ascii=False).encode("utf-8")
        suffix = ".json"
    else:
        content = df.to_csv(index=False).encode("utf-8")
        suffix = ".csv"

    filename = save_file(content, suffix=suffix, prefix=f"output_{output_cfg.name}_")

    return OutputResult(
        name=output_cfg.name,
        type="file",
        data={
            "filename": filename,
            "format": fmt,
            "download_url": f"/api/v1/file/download/{filename}",
            "row_count": len(df),
            "column_count": len(df.columns),
        },
    )


def _assemble_summary(output_cfg: OutputConfig, df: pd.DataFrame) -> OutputResult:
    """摘要输出 — 为 Agent 设计的简洁 JSON 摘要"""
    config = output_cfg.config or {}
    max_rows = config.get("max_rows", 20)

    # 基本统计信息
    summary_data: Dict[str, Any] = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }

    # 数值列摘要
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        summary_data["numeric_summary"] = {}
        for col in numeric_cols[:10]:  # 最多 10 列
            col_data = df[col].dropna()
            summary_data["numeric_summary"][col] = {
                "min": float(col_data.min()) if len(col_data) > 0 else None,
                "max": float(col_data.max()) if len(col_data) > 0 else None,
                "mean": float(col_data.mean()) if len(col_data) > 0 else None,
                "count": int(col_data.count()),
            }

    # 前 N 行数据预览
    preview_df = df.head(max_rows).replace({np.nan: None, np.inf: None, -np.inf: None})
    summary_data["preview"] = preview_df.to_dict(orient="records")

    return OutputResult(
        name=output_cfg.name,
        type="summary",
        data=summary_data,
    )
