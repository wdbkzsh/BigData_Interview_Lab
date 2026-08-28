from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[3] = BigData_Interview_Lab/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# <项目根目录>/data/app.db
DATABASE_PATH = PROJECT_ROOT / "data" / "app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "BigData Interview Lab"
    APP_ENV: str = "development"
    APP_TIMEZONE: str = "Asia/Shanghai"
    DATABASE_URL: str = f"sqlite:///{DATABASE_PATH.as_posix()}"


settings = Settings()