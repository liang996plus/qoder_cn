"""SQLite 数据集管理 — 接收上游系统数据文件并持久化为 SQLite 表

每个上传的数据文件对应 SQLite 中的一张表，_datasets 元数据表统一追踪所有已入库数据集。
现有 DatabaseConnector（driver: sqlite）可直接查询这些表供 Pipeline 消费。
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)


# ── 内部工具 ────────────────────────────────────────────────────

def _db_path() -> Path:
    """获取数据库文件路径，目录不存在则自动创建"""
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    """新建 sqlite3 连接（每次调用独立连接，避免跨线程问题）"""
    conn = sqlite3.connect(
        str(_db_path()),
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    return conn


def _sanitize_table_name(name: str) -> str:
    """清洗表名，确保为合法 SQLite 标识符"""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not name or name[0].isdigit():
        name = f"t_{name}"
    return name[:64]


def _generate_table_name(prefix: str = "ds") -> str:
    """生成唯一表名，如 ds_a1b2c3d4"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ── 初始化 ───────────────────────────────────────────────────────

async def init_db() -> None:
    """创建 _datasets 元数据表（应用启动时调用）"""

    def _do():
        conn = _connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _datasets (
                    id           TEXT PRIMARY KEY,
                    table_name   TEXT UNIQUE NOT NULL,
                    filename     TEXT,
                    description  TEXT,
                    row_count    INTEGER,
                    column_count INTEGER,
                    columns      TEXT,
                    dtypes       TEXT,
                    file_type    TEXT,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_do)
    logger.info("SQLite 数据集库初始化完成: %s", _db_path())


# ── 写入 ─────────────────────────────────────────────────────────

async def ingest_dataframe(
    df: pd.DataFrame,
    table_name: Optional[str] = None,
    filename: str = "",
    description: str = "",
    file_type: str = "",
    encoding: Optional[str] = None,
    mode: str = "create",
) -> Dict[str, Any]:
    """
    将 DataFrame 入库为 SQLite 表，返回数据集元信息字典。

    mode:
      - "create" (默认): 新建表，表名已存在时报错
      - "append"        : 追加行到已有表，列名不匹配或表不存在时报错
    """
    from app.core.errors import AppException
    from app.core.response import ErrorCode

    if df.empty:
        raise AppException(code=ErrorCode.DATA_EMPTY, message="入库数据为空")
    if mode not in ("create", "append"):
        raise AppException(code=ErrorCode.DATASET_ERROR, message=f"不支持的入库模式: {mode}")

    columns = df.columns.tolist()
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

    # ── append 模式：校验目标表是否存在、列是否兼容 ──────────────
    if mode == "append":
        if not table_name:
            raise AppException(
                code=ErrorCode.DATASET_ERROR,
                message="append 模式必须指定 table_name",
            )
        safe_name = _sanitize_table_name(table_name)
        existing = await _get_by_table_name(safe_name)
        if existing is None:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"追加目标表不存在: {safe_name}",
            )
        existing_cols = existing["columns"].split(",")
        missing = [c for c in existing_cols if c not in columns]
        if missing:
            raise AppException(
                code=ErrorCode.DATASET_ERROR,
                message=f"追加数据缺少必要列: {missing}",
            )
        tid = existing["id"]
    else:
        tid = uuid.uuid4().hex[:8]
        safe_name = _sanitize_table_name(table_name) if table_name else _generate_table_name()

    def _do():
        conn = _connect()
        try:
            if mode == "append":
                conn.execute(
                    "UPDATE _datasets SET row_count = row_count + ? WHERE id = ?",
                    (len(df), tid),
                )
            else:
                conn.execute(
                    """INSERT INTO _datasets
                       (id, table_name, filename, description,
                        row_count, column_count, columns, dtypes, file_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tid, safe_name, filename, description,
                        len(df), len(columns),
                        ",".join(columns), str(dtypes), file_type,
                    ),
                )
            conn.commit()
            engine = create_engine(f"sqlite:///{_db_path()}")
            try:
                if_exists = "append" if mode == "append" else "replace"
                df.to_sql(safe_name, engine, if_exists=if_exists, index=False)
            finally:
                engine.dispose()
        finally:
            conn.close()

    await asyncio.to_thread(_do)
    logger.info(
        "数据集%s入库完成: table=%s, rows=%d",
        "追加" if mode == "append" else "", safe_name, len(df),
    )

    return {
        "id": tid,
        "table_name": safe_name,
        "filename": filename,
        "description": description,
        "row_count": len(df),
        "column_count": len(columns),
        "columns": columns,
        "dtypes": dtypes,
        "file_type": file_type,
        "mode": mode,
    }


# ── 读取 ─────────────────────────────────────────────────────────

async def list_datasets() -> List[Dict[str, Any]]:
    """列出所有已入库数据集"""

    def _do():
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM _datasets ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    return await asyncio.to_thread(_do)


async def get_dataset(dataset_id: str, preview: int = 0) -> Optional[Dict[str, Any]]:
    """
    获取单个数据集详情。
    preview > 0 时额外返回前 N 行数据预览。
    数据集不存在时返回 None。
    """

    def _do():
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM _datasets WHERE id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            if preview > 0:
                tbl = result["table_name"]
                rows = conn.execute(
                    f'SELECT * FROM "{tbl}" LIMIT ?', (preview,)
                ).fetchall()
                result["preview"] = [list(r) for r in rows]
            return result
        finally:
            conn.close()

    return await asyncio.to_thread(_do)


# ── 查询 ─────────────────────────────────────────────────────────

async def _get_by_table_name(table_name: str) -> Optional[Dict[str, Any]]:
    """按表名查找数据集元信息（内部使用），不存在返回 None"""

    def _do():
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM _datasets WHERE table_name = ?", (table_name,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    return await asyncio.to_thread(_do)

_DANGEROUS_SQL = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|REPLACE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


async def query_dataset(sql: str) -> Dict[str, Any]:
    """
    对 SQLite 库中的数据执行只读 SELECT 查询，返回 {columns, data, row_count}。
    安全限制：仅允许 SELECT / WITH 开头的语句。
    """
    from app.core.errors import AppException
    from app.core.response import ErrorCode

    if _DANGEROUS_SQL.search(sql):
        raise AppException(
            code=ErrorCode.SQL_EXECUTION_ERROR,
            message="SQL 安全限制：仅允许 SELECT 查询",
        )

    sql_stripped = sql.strip().lstrip('\ufeff"\'').strip().upper()
    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH"):
        raise AppException(
            code=ErrorCode.SQL_EXECUTION_ERROR,
            message="SQL 必须以 SELECT 或 WITH 开头",
        )

    db_file = str(_db_path())

    def _do():
        engine = create_engine(f"sqlite:///{db_file}")
        try:
            result_df = pd.read_sql(text(sql), engine)
            return result_df
        finally:
            engine.dispose()

    result_df = await asyncio.to_thread(_do)
    columns = result_df.columns.tolist()
    data = result_df.values.tolist()
    return {"columns": columns, "data": data, "row_count": len(result_df)}


# ── 删除 ─────────────────────────────────────────────────────────

async def delete_dataset(dataset_id: str) -> bool:
    """删除数据集（元数据记录 + 对应 SQLite 表），不存在时返回 False"""

    def _do():
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT table_name FROM _datasets WHERE id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                return False
            conn.execute(f'DROP TABLE IF EXISTS "{row["table_name"]}"')
            conn.execute("DELETE FROM _datasets WHERE id = ?", (dataset_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    result = await asyncio.to_thread(_do)
    if result:
        logger.info("数据集已删除: id=%s", dataset_id)
    return result

