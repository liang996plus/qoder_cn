"""应用配置管理，从环境变量 / .env 文件读取"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "hiagent-web-service"
    file_storage_path: str = "./tmp_files"
    file_cleanup_interval_hours: int = 2
    app_port: int = 8080
    log_level: str = "INFO"
    scenarios_dir: str = "./app/scenarios"
    db_path: str = "./data/hiagent.db"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
