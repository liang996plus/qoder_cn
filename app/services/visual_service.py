"""可视化业务逻辑"""

from __future__ import annotations

import base64
import io
import math
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # 无头模式
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

from app.core.errors import AppException
from app.core.file_manager import save_file
from app.core.response import ErrorCode
from app.models.data_models import DataFrameInput
from app.models.visual_models import (
    ChartConfig,
    ChartType,
    ConditionalStyle,
    OutputFormat,
    TableConfig,
)
from app.services.data_service import input_to_df


# ── 中文字体设置 ────────────────────────────────────────────────

def _setup_chinese_font() -> None:
    """尝试设置中文字体支持"""
    chinese_fonts = [
        "SimHei", "Microsoft YaHei", "PingFang SC",
        "Noto Sans CJK SC", "WenQuanYi Micro Hei",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font_name in chinese_fonts:
        if font_name in available:
            plt.rcParams["font.sans-serif"] = [font_name] + plt.rcParams["font.sans-serif"]
            plt.rcParams["axes.unicode_minus"] = False
            return

_setup_chinese_font()


# ── 图表生成 ──────────────────────────────────────────────────

def generate_chart(
    df: pd.DataFrame,
    config: ChartConfig,
    output_format: OutputFormat,
) -> Dict[str, Any]:
    """根据配置生成图表"""
    chart_func_map = {
        ChartType.BAR: _chart_bar,
        ChartType.LINE: _chart_line,
        ChartType.PIE: _chart_pie,
        ChartType.SCATTER: _chart_scatter,
        ChartType.HEATMAP: _chart_heatmap,
        ChartType.RADAR: _chart_radar,
        ChartType.AREA: _chart_area,
        ChartType.HISTOGRAM: _chart_histogram,
        ChartType.BOX: _chart_box,
    }

    chart_func = chart_func_map.get(config.chart_type)
    if chart_func is None:
        raise AppException(
            code=ErrorCode.CHART_TYPE_UNSUPPORTED,
            message=f"不支持的图表类型: {config.chart_type}",
        )

    try:
        if output_format == OutputFormat.HTML:
            return _generate_html_chart(df, config)
        else:
            return _generate_matplotlib_chart(df, config, output_format, chart_func)
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            code=ErrorCode.RENDER_FAILED,
            message=f"图表渲染失败: {str(e)}",
        )


def _generate_matplotlib_chart(
    df: pd.DataFrame,
    config: ChartConfig,
    output_format: OutputFormat,
    chart_func: Any,
) -> Dict[str, Any]:
    """使用 matplotlib 生成 PNG/SVG 图表"""
    fig, ax = plt.subplots(
        figsize=(config.width / 100, config.height / 100),
        dpi=100,
    )

    chart_func(df, config, ax)

    if config.title:
        ax.set_title(config.title, fontsize=14, fontweight="bold")
    if config.xlabel:
        ax.set_xlabel(config.xlabel)
    if config.ylabel:
        ax.set_ylabel(config.ylabel)

    # 坐标轴配置
    if config.x_axis:
        if config.x_axis.tick_rotation is not None:
            plt.xticks(rotation=config.x_axis.tick_rotation)
        if config.x_axis.label:
            ax.set_xlabel(config.x_axis.label)
    if config.y_axis:
        if config.y_axis.label:
            ax.set_ylabel(config.y_axis.label)
        if config.y_axis.min_value is not None or config.y_axis.max_value is not None:
            ax.set_ylim(
                bottom=config.y_axis.min_value,
                top=config.y_axis.max_value,
            )

    plt.tight_layout()

    buf = io.BytesIO()
    if output_format == OutputFormat.SVG:
        fig.savefig(buf, format="svg", bbox_inches="tight")
        image_str = buf.getvalue().decode("utf-8")
    else:
        fig.savefig(buf, format="png", bbox_inches="tight")
        image_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    plt.close(fig)

    # 同时保存到临时文件
    suffix = ".svg" if output_format == OutputFormat.SVG else ".png"
    filename = save_file(buf.getvalue(), suffix=suffix, prefix="chart_")

    return {
        "image_base64": image_str,
        "html_content": None,
        "filename": filename,
        "output_format": output_format.value,
    }


def _generate_html_chart(df: pd.DataFrame, config: ChartConfig) -> Dict[str, Any]:
    """使用 plotly 生成交互式 HTML 图表"""
    import plotly.express as px
    import plotly.graph_objects as go

    y_cols = config.y if isinstance(config.y, list) else ([config.y] if config.y else [])

    if config.chart_type == ChartType.BAR:
        if len(y_cols) > 1:
            fig = px.bar(df, x=config.x, y=y_cols, title=config.title or "", barmode="group")
        else:
            fig = px.bar(df, x=config.x, y=y_cols[0] if y_cols else None, title=config.title or "")
    elif config.chart_type == ChartType.LINE:
        if len(y_cols) > 1:
            fig = px.line(df, x=config.x, y=y_cols, title=config.title or "")
        else:
            fig = px.line(df, x=config.x, y=y_cols[0] if y_cols else None, title=config.title or "")
    elif config.chart_type == ChartType.PIE:
        fig = px.pie(df, names=config.x, values=y_cols[0] if y_cols else None, title=config.title or "")
    elif config.chart_type == ChartType.SCATTER:
        fig = px.scatter(
            df, x=config.x, y=y_cols[0] if y_cols else None,
            title=config.title or "",
        )
    elif config.chart_type == ChartType.HEATMAP:
        numeric_df = df.select_dtypes(include=[np.number])
        fig = px.imshow(numeric_df.corr(), title=config.title or "", text_auto=True)
    elif config.chart_type == ChartType.AREA:
        fig = px.area(df, x=config.x, y=y_cols, title=config.title or "")
    elif config.chart_type == ChartType.HISTOGRAM:
        fig = px.histogram(df, x=config.x, title=config.title or "")
    elif config.chart_type == ChartType.BOX:
        fig = px.box(df, x=config.x, y=y_cols[0] if y_cols else None, title=config.title or "")
    else:
        raise AppException(
            code=ErrorCode.CHART_TYPE_UNSUPPORTED,
            message=f"HTML 模式不支持的图表类型: {config.chart_type}",
        )

    fig.update_layout(width=config.width, height=config.height)
    if config.xlabel:
        fig.update_xaxes(title_text=config.xlabel)
    if config.ylabel:
        fig.update_yaxes(title_text=config.ylabel)
    if config.colors:
        fig.update_layout(colorway=config.colors)

    html_content = fig.to_html(full_html=True, include_plotlyjs="cdn")
    filename = save_file(html_content.encode("utf-8"), suffix=".html", prefix="chart_")

    return {
        "image_base64": None,
        "html_content": html_content,
        "filename": filename,
        "output_format": "html",
    }


# ── matplotlib 图表绘制函数 ────────────────────────────────────

def _chart_bar(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    y_cols = config.y if isinstance(config.y, list) else [config.y]
    x_data = df[config.x] if config.x else df.index
    x_pos = np.arange(len(x_data))
    width = 0.8 / len(y_cols)

    for i, col in enumerate(y_cols):
        offset = (i - len(y_cols) / 2 + 0.5) * width
        bars = ax.bar(x_pos + offset, df[col], width, label=col, color=config.colors[i] if config.colors and i < len(config.colors) else None)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_data)
    if len(y_cols) > 1:
        ax.legend()


def _chart_line(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    y_cols = config.y if isinstance(config.y, list) else [config.y]
    x_data = df[config.x] if config.x else df.index

    for i, col in enumerate(y_cols):
        color = config.colors[i] if config.colors and i < len(config.colors) else None
        ax.plot(x_data, df[col], marker="o", label=col, color=color)

    if len(y_cols) > 1:
        ax.legend()
    ax.grid(True, alpha=0.3)


def _chart_pie(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    y_col = config.y if isinstance(config.y, str) else (config.y[0] if config.y else None)
    if not y_col or not config.x:
        raise AppException(code=ErrorCode.PARAM_VALIDATION_ERROR, message="饼图需要指定 x（标签列）和 y（数值列）")

    values = df[y_col]
    labels = df[config.x]
    colors = config.colors[:len(values)] if config.colors else None

    ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")


def _chart_scatter(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    y_col = config.y if isinstance(config.y, str) else (config.y[0] if config.y else None)
    if not config.x or not y_col:
        raise AppException(code=ErrorCode.PARAM_VALIDATION_ERROR, message="散点图需要指定 x 和 y 列")

    color = config.colors[0] if config.colors else None
    ax.scatter(df[config.x], df[y_col], color=color, alpha=0.7, edgecolors="black", linewidth=0.5)
    ax.grid(True, alpha=0.3)


def _chart_heatmap(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    numeric_df = df.select_dtypes(include=[np.number])
    corr = numeric_df.corr()
    im = ax.imshow(corr.values, cmap="RdYlBu_r", aspect="auto")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.columns)
    plt.colorbar(im, ax=ax)


def _chart_radar(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    """雷达图"""
    numeric_df = df.select_dtypes(include=[np.number])
    categories = numeric_df.columns.tolist()
    N = len(categories)

    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    ax = plt.subplot(111, polar=True)
    for idx, row in numeric_df.iterrows():
        values = row.tolist()
        values += values[:1]
        label = str(df.iloc[idx][config.x]) if config.x and config.x in df.columns else f"Series {idx}"
        ax.plot(angles, values, "o-", linewidth=2, label=label)
        ax.fill(angles, values, alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))


def _chart_area(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    y_cols = config.y if isinstance(config.y, list) else [config.y]
    x_data = df[config.x] if config.x else df.index

    for i, col in enumerate(y_cols):
        color = config.colors[i] if config.colors and i < len(config.colors) else None
        ax.fill_between(x_data, df[col], alpha=0.4, label=col, color=color)
        ax.plot(x_data, df[col], linewidth=1.5, color=color)

    if len(y_cols) > 1:
        ax.legend()
    ax.grid(True, alpha=0.3)


def _chart_histogram(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    if not config.x:
        raise AppException(code=ErrorCode.PARAM_VALIDATION_ERROR, message="直方图需要指定 x 列")
    bins = (config.extra or {}).get("bins", 20)
    color = config.colors[0] if config.colors else None
    ax.hist(df[config.x].dropna(), bins=bins, color=color, edgecolor="black", alpha=0.7)
    ax.grid(True, axis="y", alpha=0.3)


def _chart_box(df: pd.DataFrame, config: ChartConfig, ax: plt.Axes) -> None:
    y_cols = config.y if isinstance(config.y, list) else [config.y]
    data_to_plot = [df[col].dropna().values for col in y_cols]
    bp = ax.boxplot(data_to_plot, patch_artist=True)

    for i, patch in enumerate(bp["boxes"]):
        if config.colors and i < len(config.colors):
            patch.set_facecolor(config.colors[i])

    ax.set_xticklabels(y_cols)
    ax.grid(True, axis="y", alpha=0.3)


# ── 表格渲染 ──────────────────────────────────────────────────

def render_table(df: pd.DataFrame, config: Optional[TableConfig] = None) -> Dict[str, Any]:
    """渲染 HTML 表格"""
    display_df = df.copy()

    if config:
        if config.sort_by and config.sort_by in display_df.columns:
            display_df = display_df.sort_values(
                by=config.sort_by, ascending=config.sort_ascending
            )
        if config.max_rows and len(display_df) > config.max_rows:
            display_df = display_df.head(config.max_rows)

    # 构建 HTML
    html_parts = []
    if config and config.title:
        html_parts.append(f'<h3 style="text-align:center">{config.title}</h3>')

    html_parts.append('<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;">')

    # 表头
    html_parts.append("<thead><tr>")
    if config and config.show_index:
        html_parts.append("<th style='background-color:#4472C4;color:white;padding:8px;'>#</th>")
    for col in display_df.columns:
        width_style = ""
        if config and config.column_widths and col in config.column_widths:
            width_style = f"width:{config.column_widths[col]};"
        html_parts.append(
            f"<th style='background-color:#4472C4;color:white;padding:8px;{width_style}'>{col}</th>"
        )
    html_parts.append("</tr></thead>")

    # 表体
    html_parts.append("<tbody>")
    for row_idx, (_, row) in enumerate(display_df.iterrows()):
        row_bg = "#f2f2f2" if row_idx % 2 == 0 else "#ffffff"
        html_parts.append(f"<tr style='background-color:{row_bg};'>")
        if config and config.show_index:
            html_parts.append(f"<td style='padding:6px;text-align:center;'>{row_idx}</td>")
        for col in display_df.columns:
            cell_value = row[col]
            cell_style = f"padding:6px;"

            # 条件样式
            if config and config.conditional_styles:
                for cs in config.conditional_styles:
                    if cs.column == col and _eval_condition(cell_value, cs.condition):
                        for k, v in cs.style.items():
                            cell_style += f"{k}:{v};"

            # NaN 显示为空
            if pd.isna(cell_value):
                cell_display = ""
            elif isinstance(cell_value, float):
                cell_display = f"{cell_value:,.2f}"
            else:
                cell_display = str(cell_value)

            html_parts.append(f"<td style='{cell_style}'>{cell_display}</td>")
        html_parts.append("</tr>")

    html_parts.append("</tbody></table>")
    html_parts.append(f"<p style='color:#666;font-size:11px;'>共 {len(df)} 行 x {len(df.columns)} 列</p>")

    return {
        "html": "\n".join(html_parts),
        "row_count": len(df),
        "column_count": len(df.columns),
    }


def _eval_condition(value: Any, condition: str) -> bool:
    """安全地评估简单条件表达式"""
    try:
        if pd.isna(value):
            return False
        # 支持的运算符: >, <, >=, <=, ==, !=
        condition = condition.strip()
        for op in (">=", "<=", "!=", "==", ">", "<"):
            if condition.startswith(op):
                threshold_str = condition[len(op):].strip()
                try:
                    threshold = float(threshold_str)
                    numeric_val = float(value)
                except (ValueError, TypeError):
                    threshold = threshold_str.strip("'\"")
                    numeric_val = str(value)

                if op == ">": return numeric_val > threshold
                if op == "<": return numeric_val < threshold
                if op == ">=": return numeric_val >= threshold
                if op == "<=": return numeric_val <= threshold
                if op == "==": return numeric_val == threshold
                if op == "!=": return numeric_val != threshold
        return False
    except Exception:
        return False
