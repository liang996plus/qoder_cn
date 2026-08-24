"""数据库连接器 — 支持 MySQL/PostgreSQL/SQLite"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict

import duckdb
import pandas as pd

from app.core.connectors.base import BaseConnector
from app.core.errors import AppException
from app.core.response import ErrorCode

logger = logging.getLogger(__name__)


class DatabaseConnector(BaseConnector):
    """
    数据库连接器，支持：
    - SQLite: 通过 DuckDB 直接查询 .db 文件
    - MySQL/PostgreSQL: 通过 SQLAlchemy 连接

    config 字段：
      driver: "sqlite" | "mysql" | "postgresql"
      # SQLite
      path: str (SQLite 文件路径)
      # MySQL/PostgreSQL
      host: str
      port: int
      user: str
      password: str
      password_env: str  (从环境变量读取密码，优先级高于 password)
      database: str
      sql: str (SELECT 查询语句)
    """

    @classmethod
    def connector_type(cls) -> str:
        return "database"

    async def fetch(self, config: Dict[str, Any]) -> pd.DataFrame:
        driver = config.get("driver", "sqlite")
        sql = config.get("sql")
        if not sql:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message="数据库连接器: 缺少 sql 配置",
            )

        try:
            if driver == "sqlite":
                return self._fetch_sqlite(config, sql)
            elif driver in ("mysql", "postgresql", "postgres"):
                return await self._fetch_sqlalchemy(config, sql, driver)
            else:
                raise AppException(
                    code=ErrorCode.CONNECTOR_ERROR,
                    message=f"数据库连接器: 不支持的驱动 '{driver}'",
                )
        except AppException:
            raise
        except Exception as e:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message=f"数据库连接器错误: {str(e)}",
            )

    def _fetch_sqlite(self, config: Dict[str, Any], sql: str) -> pd.DataFrame:
        """通过 DuckDB 查询 SQLite 文件"""
        db_path = config.get("path")
        if not db_path:
            raise AppException(
                code=ErrorCode.CONNECTOR_ERROR,
                message="SQLite 连接器: 缺少 path 配置",
            )
        con = duckdb.connect(":memory:")
        try:
            con.execute(f"ATTACH '{db_path}' AS sqlite_db (TYPE SQLITE)")
            result = con.execute(sql).fetchdf()
            return result
        finally:
            con.close()

    async def _fetch_sqlalchemy(
        self, config: Dict[str, Any], sql: str, driver: str
    ) -> pd.DataFrame:
        """通过 SQLAlchemy 连接 MySQL/PostgreSQL"""
        from sqlalchemy import create_engine, text

        host = config.get("host", "localhost")
        port = config.get("port", 3306 if driver == "mysql" else 5432)
        user = config.get("user", "root")
        # 密码优先从环境变量读取
        password_env = config.get("password_env")
        password = os.environ.get(password_env) if password_env else config.get("password", "")
        database = config.get("database", "")

        if driver == "mysql":
            url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        else:
            url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                result = pd.read_sql(text(sql), conn)
                return result
        finally:
            engine.dispose()
