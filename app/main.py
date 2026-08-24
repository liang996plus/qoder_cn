"""hiagent 辅助 Web 服务 — FastAPI 入口"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.core.errors import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.core.file_manager import get_file_path, periodic_cleanup
from app.core import db as db_manager
from app.api.v1.router import router as v1_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动：初始化 SQLite 数据集库 + 后台清理任务
    await db_manager.init_db()
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("应用启动完成，SQLite 数据集库已初始化，临时文件清理任务已启动")
    yield
    # 关闭：取消后台任务
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title=settings.app_name,
        description="hiagent 辅助 Web 服务 — 为 AI Agent 提供数据处理、可视化、文件生成等能力",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── 中间件 ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── request_id 注入中间件 ──
    @app.middleware("http")
    async def inject_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── 异常处理器 ──
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # ── 路由 ──
    app.include_router(v1_router)

    # ── 文件下载接口 ──
    @app.get("/api/v1/file/download/{filename}", tags=["文件下载"])
    async def download_file(filename: str):
        filepath = get_file_path(filename)
        if filepath is None:
            from app.core.errors import AppException
            from app.core.response import ErrorCode
            raise AppException(code=ErrorCode.FILE_NOT_FOUND, message=f"文件不存在: {filename}")
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="application/octet-stream",
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=True,
    )
