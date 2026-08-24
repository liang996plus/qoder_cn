"""统一响应模型与错误码定义"""

from __future__ import annotations

import uuid
from enum import IntEnum
from typing import Any, Optional

from pydantic import BaseModel


class ErrorCode(IntEnum):
    """错误码枚举，按模块分段"""

    # 成功
    SUCCESS = 0

    # 1xxx — 通用错误
    PARAM_VALIDATION_ERROR = 1001
    RESOURCE_NOT_FOUND = 1003

    # 2xxx — 数据处理
    FILE_PARSE_ERROR = 2001
    SQL_EXECUTION_ERROR = 2002
    DATA_EMPTY = 2003
    DATA_TYPE_ERROR = 2004
    DATASET_ERROR = 2005

    # 3xxx — 可视化
    CHART_TYPE_UNSUPPORTED = 3001
    RENDER_FAILED = 3002

    # 4xxx — 文件文档
    FILE_NOT_FOUND = 4001
    FILE_FORMAT_ERROR = 4002
    REPORT_GENERATION_FAILED = 4003

    # 5xxx — API 编排
    PROXY_REQUEST_FAILED = 5001
    PROXY_TIMEOUT = 5002

    # 6xxx — Pipeline 引擎
    SCENARIO_NOT_FOUND = 6001
    PIPELINE_STEP_FAILED = 6002
    CONNECTOR_ERROR = 6003


# 错误码对应的默认消息
_ERROR_MESSAGES: dict[int, str] = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.PARAM_VALIDATION_ERROR: "参数校验失败",
    ErrorCode.RESOURCE_NOT_FOUND: "资源不存在",
    ErrorCode.FILE_PARSE_ERROR: "文件解析失败",
    ErrorCode.SQL_EXECUTION_ERROR: "SQL 执行错误",
    ErrorCode.DATA_EMPTY: "数据为空",
    ErrorCode.DATA_TYPE_ERROR: "数据类型错误",
    ErrorCode.DATASET_ERROR: "数据集操作错误",
    ErrorCode.CHART_TYPE_UNSUPPORTED: "图表类型不支持",
    ErrorCode.RENDER_FAILED: "渲染失败",
    ErrorCode.FILE_NOT_FOUND: "文件不存在",
    ErrorCode.FILE_FORMAT_ERROR: "文件格式错误",
    ErrorCode.REPORT_GENERATION_FAILED: "报表生成失败",
    ErrorCode.PROXY_REQUEST_FAILED: "代理请求失败",
    ErrorCode.PROXY_TIMEOUT: "代理请求超时",
    ErrorCode.SCENARIO_NOT_FOUND: "场景配置不存在",
    ErrorCode.PIPELINE_STEP_FAILED: "流水线步骤执行失败",
    ErrorCode.CONNECTOR_ERROR: "数据连接器错误",
}


class ApiResponse(BaseModel):
    """统一响应体"""

    code: int = ErrorCode.SUCCESS
    message: str = "success"
    data: Optional[Any] = None
    request_id: str = ""

    @classmethod
    def success(cls, data: Any = None, request_id: str | None = None) -> ApiResponse:
        return cls(
            code=ErrorCode.SUCCESS,
            message="success",
            data=data,
            request_id=request_id or str(uuid.uuid4()),
        )

    @classmethod
    def error(
        cls,
        code: int | ErrorCode,
        message: str | None = None,
        data: Any = None,
        request_id: str | None = None,
    ) -> ApiResponse:
        code = int(code)
        return cls(
            code=code,
            message=message or _ERROR_MESSAGES.get(code, "未知错误"),
            data=data,
            request_id=request_id or str(uuid.uuid4()),
        )
