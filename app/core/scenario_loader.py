"""YAML 场景配置加载器"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from app.config import settings
from app.core.errors import AppException
from app.core.response import ErrorCode

logger = logging.getLogger(__name__)


# ── 场景配置 Pydantic 模型 ─────────────────────────────────────

class DataSourceConfig(BaseModel):
    """数据源定义"""
    name: str
    connector: str
    config: Dict[str, Any] = Field(default_factory=dict)


class PipelineStepConfig(BaseModel):
    """流水线步骤定义"""
    name: str
    action: str
    input: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    on_error: str = "abort"  # skip / abort
    condition: Optional[str] = None  # 简单条件表达式


class OutputConfig(BaseModel):
    """输出定义"""
    name: str
    type: str  # chart / table / file / summary
    source: str
    config: Dict[str, Any] = Field(default_factory=dict)


class ScenarioConfig(BaseModel):
    """完整场景配置"""
    scenario_id: str
    name: str
    description: str = ""
    version: str = "1.0"
    data_sources: List[DataSourceConfig] = Field(default_factory=list)
    pipeline: List[PipelineStepConfig] = Field(default_factory=list)
    outputs: List[OutputConfig] = Field(default_factory=list)


# ── 加载器 ────────────────────────────────────────────────────

def _get_scenarios_dir() -> Path:
    """获取场景配置目录"""
    scenarios_dir = Path(settings.scenarios_dir)
    if not scenarios_dir.exists():
        scenarios_dir.mkdir(parents=True, exist_ok=True)
    return scenarios_dir


def load_scenario(scenario_id: str) -> ScenarioConfig:
    """从 YAML 文件加载场景配置"""
    scenarios_dir = _get_scenarios_dir()
    yaml_path = scenarios_dir / f"{scenario_id}.yaml"

    if not yaml_path.exists():
        raise AppException(
            code=ErrorCode.SCENARIO_NOT_FOUND,
            message=f"场景配置不存在: '{scenario_id}' (查找路径: {yaml_path})",
        )

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise AppException(
            code=ErrorCode.SCENARIO_NOT_FOUND,
            message=f"场景配置 YAML 解析失败: {str(e)}",
        )

    if not isinstance(raw, dict):
        raise AppException(
            code=ErrorCode.SCENARIO_NOT_FOUND,
            message="场景配置格式错误: YAML 根节点必须为字典",
        )

    # 确保 scenario_id 一致
    raw.setdefault("scenario_id", scenario_id)

    try:
        config = ScenarioConfig(**raw)
    except Exception as e:
        raise AppException(
            code=ErrorCode.SCENARIO_NOT_FOUND,
            message=f"场景配置校验失败: {str(e)}",
        )

    return config


def list_scenarios() -> List[Dict[str, str]]:
    """列出所有可用场景"""
    scenarios_dir = _get_scenarios_dir()
    result = []

    for yaml_file in sorted(scenarios_dir.glob("*.yaml")):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if isinstance(raw, dict):
                result.append({
                    "scenario_id": raw.get("scenario_id", yaml_file.stem),
                    "name": raw.get("name", yaml_file.stem),
                    "description": raw.get("description", ""),
                    "version": raw.get("version", "1.0"),
                })
        except Exception as e:
            logger.warning("加载场景配置失败 %s: %s", yaml_file.name, str(e))

    return result
