"""连接器抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class BaseConnector(ABC):
    """所有数据连接器的抽象基类，子类必须实现 fetch 和 connector_type"""

    @abstractmethod
    async def fetch(self, config: Dict[str, Any]) -> pd.DataFrame:
        """根据配置获取数据，返回统一的 DataFrame"""
        ...

    @classmethod
    @abstractmethod
    def connector_type(cls) -> str:
        """连接器类型标识，如 'database'、'api'、'file_upload'"""
        ...
