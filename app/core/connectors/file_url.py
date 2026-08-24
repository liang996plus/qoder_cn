"""URL 文件下载连接器 — 从 URL 下载文件并解析"""

from __future__ import annotations

import logging
from typing import Any, Dict
from urllib.parse import urlparse

import httpx
import pandas as pd

from app.core.connectors.base import BaseConnector
from app.core.errors import AppException
from app.core.response import ErrorCode

logger = logging.getLogger(__name__)


class FileUrlConnector(BaseConnector):
    """
    URL 文件下载连接器

    config 字段：
      url: str (文件下载地址)
      filename: str (可选，用于判断文件格式；为空则从 URL 推断)
      headers: dict (可选，请求头)
      timeout: float (超时秒数，默认 60)
    """

    @classmethod
    def connector_type(cls) -> str:
        return "file_url"

    async def fetch(self, config: Dict[str, Any]) -> pd.DataFrame:
        url = config.get("url")
        if not url:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message="URL 文件连接器: 缺少 url 配置",
            )

        filename = config.get("filename") or self._guess_filename(url)
        headers = config.get("headers", {})
        timeout = config.get("timeout", 60)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                content = resp.content
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message=f"URL 文件连接器: 下载失败: {str(e)}",
            )

        # 复用 data_service 的解析逻辑
        from app.services.data_service import parse_file

        try:
            result = parse_file(content, filename)
            df = pd.DataFrame(result["data"], columns=result["columns"])
            return df
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message=f"URL 文件连接器: 文件解析失败: {str(e)}",
            )

    @staticmethod
    def _guess_filename(url: str) -> str:
        """从 URL 推断文件名"""
        path = urlparse(url).path
        if path and "/" in path:
            name = path.rsplit("/", 1)[-1]
            if name and "." in name:
                return name
        return "data.csv"  # 默认 CSV
