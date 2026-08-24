"""连接器注册表 — 注册表模式管理所有连接器"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from app.core.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """连接器注册表，单例模式"""

    _connectors: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, connector_cls: Type[BaseConnector]) -> Type[BaseConnector]:
        """注册连接器（可用作装饰器）"""
        type_name = connector_cls.connector_type()
        if type_name in cls._connectors:
            logger.warning("连接器类型 '%s' 已被覆盖", type_name)
        cls._connectors[type_name] = connector_cls
        return connector_cls

    @classmethod
    def get(cls, type_name: str) -> BaseConnector:
        """获取连接器实例"""
        connector_cls = cls._connectors.get(type_name)
        if connector_cls is None:
            available = ", ".join(cls._connectors.keys())
            raise ValueError(
                f"未知的连接器类型: '{type_name}'。可用类型: {available}"
            )
        return connector_cls()

    @classmethod
    def list_types(cls) -> List[str]:
        """列出所有已注册的连接器类型"""
        return list(cls._connectors.keys())

    @classmethod
    def has(cls, type_name: str) -> bool:
        return type_name in cls._connectors


# ── 导入并注册所有连接器 ──────────────────────────────────────
# 放在模块末尾，确保 BaseConnector 已定义

from app.core.connectors.database import DatabaseConnector  # noqa: E402
from app.core.connectors.api_connector import ApiConnector  # noqa: E402
from app.core.connectors.file_upload import FileUploadConnector  # noqa: E402
from app.core.connectors.file_url import FileUrlConnector  # noqa: E402

ConnectorRegistry.register(DatabaseConnector)
ConnectorRegistry.register(ApiConnector)
ConnectorRegistry.register(FileUploadConnector)
ConnectorRegistry.register(FileUrlConnector)
