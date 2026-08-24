"""临时文件管理 — 存储、下载、定时清理"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings


def get_storage_path() -> Path:
    """获取临时文件存储目录，不存在则创建"""
    path = Path(settings.file_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_file(content: bytes, suffix: str = "", prefix: str = "") -> str:
    """保存临时文件，返回文件名（不含路径）"""
    filename = f"{prefix}{uuid.uuid4().hex}{suffix}"
    filepath = get_storage_path() / filename
    filepath.write_bytes(content)
    return filename


def get_file_path(filename: str) -> Optional[Path]:
    """获取文件完整路径，不存在返回 None"""
    filepath = get_storage_path() / filename
    if filepath.is_file():
        return filepath
    return None


def delete_file(filename: str) -> bool:
    """删除指定临时文件"""
    filepath = get_storage_path() / filename
    if filepath.is_file():
        filepath.unlink()
        return True
    return False


def cleanup_expired_files() -> int:
    """清理过期的临时文件，返回删除的文件数"""
    storage = get_storage_path()
    max_age_seconds = settings.file_cleanup_interval_hours * 3600
    now = time.time()
    deleted = 0

    for filepath in storage.iterdir():
        if filepath.is_file():
            age = now - filepath.stat().st_mtime
            if age > max_age_seconds:
                filepath.unlink()
                deleted += 1

    return deleted


async def periodic_cleanup(interval_seconds: int = 1800) -> None:
    """后台定时清理任务，默认每 30 分钟执行一次"""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            deleted = cleanup_expired_files()
            if deleted > 0:
                import logging
                logging.getLogger(__name__).info(
                    "已清理 %d 个过期临时文件", deleted
                )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("临时文件清理失败")
