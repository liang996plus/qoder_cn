"""Pipeline 相关 Pydantic 模型"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    """Pipeline 执行请求"""
    scenario_id: str = Field(..., description="场景 ID，对应 YAML 文件名（不含扩展名）")
    params: Dict[str, Any] = Field(default_factory=dict, description="场景参数")


class PipelineStepResult(BaseModel):
    """单个步骤执行结果"""
    step_name: str
    status: str  # success / skipped / failed
    duration_ms: float = 0.0
    message: str = ""


class OutputResult(BaseModel):
    """单个输出结果"""
    name: str
    type: str  # chart / table / file / summary
    data: Any = None


class PipelineRunResponse(BaseModel):
    """Pipeline 执行响应"""
    scenario_id: str
    steps: List[PipelineStepResult]
    outputs: List[OutputResult]
    total_duration_ms: float


class ScenarioListItem(BaseModel):
    """场景列表项"""
    scenario_id: str
    name: str
    description: str
    version: str
