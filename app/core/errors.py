"""自定义异常与全局异常处理器"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import ApiResponse, ErrorCode


class AppException(Exception):
    """业务异常，携带错误码和详情"""

    def __init__(
        self,
        code: int | ErrorCode = ErrorCode.PARAM_VALIDATION_ERROR,
        message: str | None = None,
        data: Any = None,
    ):
        self.code = int(code)
        self.message = message
        self.data = data
        super().__init__(message or "")


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理自定义业务异常"""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    response = ApiResponse.error(
        code=exc.code,
        message=exc.message,
        data=exc.data,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 Pydantic 参数校验异常"""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors = exc.errors()
    response = ApiResponse.error(
        code=ErrorCode.PARAM_VALIDATION_ERROR,
        message=f"参数校验失败: {errors}",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=422,
        content=response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未预期的异常"""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    response = ApiResponse.error(
        code=ErrorCode.PARAM_VALIDATION_ERROR,
        message=f"服务器内部错误: {type(exc).__name__}",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=500,
        content=response.model_dump(),
    )
