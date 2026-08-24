"""文件上传连接器 — 接收 base64 编码的文件内容并解析"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict

import pandas as pd

from app.core.connectors.base import BaseConnector
from app.core.errors import AppException
from app.core.response import ErrorCode

logger = logging.getLogger(__name__)


class FileUploadConnector(BaseConnector):
    """
    文件上传连接器

    config 字段：
      file_content: str (base64 编码的文件内容)
      filename: str (文件名，用于判断格式)
    """

    @classmethod
    def connector_type(cls) -> str:
        return "file_upload"

    async def fetch(self, config: Dict[str, Any]) -> pd.DataFrame:
        file_content_b64 = config.get("file_content")
        filename = config.get("filename", "data.csv")

        if not file_content_b64:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message="文件上传连接器: 缺少 file_content 配置",
            )

        try:
            content = base64.b64decode(file_content_b64)
        except Exception as e:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message=f"文件上传连接器: base64 解码失败: {str(e)}",
            )

        # 复用 data_service 的解析逻辑
        from app.services.data_service import parse_file

        try:
            result = parse_file(content, filename)
            # parse_file 返回的 result 包含 columns 和 data
            df = pd.DataFrame(result["data"], columns=result["columns"])
            return df
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message=f"文件上传连接器: 文件解析失败: {str(e)}",
            )
