"""测试公共配置"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def test_db(tmp_path_factory):
    """会话级别临时 SQLite 数据库，避免测试污染真实数据"""
    db_dir = tmp_path_factory.mktemp("test_data")
    original = settings.db_path
    settings.db_path = str(db_dir / "test.db")
    yield settings.db_path
    settings.db_path = original


@pytest.fixture
def client():
    """FastAPI 测试客户端（使用 context manager 确保 lifespan 正常运行）"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_dataframe_input():
    """示例 DataFrameInput 请求体"""
    return {
        "dataframe": {
            "columns": ["name", "age", "score", "city"],
            "data": [
                ["Alice", 25, 88.5, "Beijing"],
                ["Bob", 30, 92.0, "Shanghai"],
                ["Charlie", 28, 76.3, "Guangzhou"],
                ["Diana", 35, 95.1, "Beijing"],
                ["Eve", 22, 83.7, "Shanghai"],
            ],
        }
    }
