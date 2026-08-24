"""REST API 连接器 — 使用 httpx 异步请求外部 API"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import httpx
import pandas as pd

from app.core.connectors.base import BaseConnector
from app.core.errors import AppException
from app.core.response import ErrorCode

logger = logging.getLogger(__name__)


class ApiConnector(BaseConnector):
    """
    REST API 连接器

    config 字段：
      url: str (请求 URL)
      method: "GET" | "POST" (默认 GET)
      headers: dict (请求头)
      params: dict (URL 查询参数)
      body: dict | list (POST 请求体)
      timeout: float (超时秒数，默认 30)
      retries: int (重试次数，默认 1)
      data_path: str (响应 JSON 中的数据路径，如 "data.items"，点号分隔)
    """

    @classmethod
    def connector_type(cls) -> str:
        return "api"

    async def fetch(self, config: Dict[str, Any]) -> pd.DataFrame:
        url = config.get("url")
        if not url:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message="API 连接器: 缺少 url 配置",
            )

        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        params = config.get("params")
        body = config.get("body")
        timeout = config.get("timeout", 30)
        retries = config.get("retries", 1)
        data_path = config.get("data_path")

        last_error: Optional[Exception] = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    if method == "GET":
                        resp = await client.get(url, headers=headers, params=params)
                    elif method == "POST":
                        resp = await client.post(
                            url, headers=headers, params=params, json=body
                        )
                    else:
                        raise AppException(
                            code=ErrorCode.CONNECTOR_ERROR,
                            message=f"API 连接器: 不支持的 HTTP 方法 '{method}'",
                        )

                    resp.raise_for_status()
                    data = resp.json()

                # 按 data_path 提取数据
                if data_path:
                    data = self._extract_by_path(data, data_path)

                # 将数据转为 DataFrame
                return self._to_dataframe(data)

            except AppException:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "API 连接器请求失败 (第 %d/%d 次): %s",
                    attempt + 1, retries, str(e),
                )
                continue

        raise AppException(
            code=ErrorCode.CONNECTOR_ERROR,
            message=f"API 连接器请求失败 (重试 {retries} 次): {str(last_error)}",
        )

    @staticmethod
    def _extract_by_path(data: Any, path: str) -> Any:
        """按点号路径提取 JSON 数据，如 'data.items'"""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None
            if current is None:
                return None
        return current

    @staticmethod
    def _to_dataframe(data: Any) -> pd.DataFrame:
        """将 JSON 数据转为 DataFrame"""
        if isinstance(data, list):
            if len(data) == 0:
                return pd.DataFrame()
            if isinstance(data[0], dict):
                return pd.DataFrame(data)
            # 列表的列表
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            # 尝试作为单行
            return pd.DataFrame([data])
        else:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message=f"API 连接器: 无法将响应数据转为 DataFrame (type={type(data).__name__})",
            )
