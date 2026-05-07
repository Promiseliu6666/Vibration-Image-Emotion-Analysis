import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


def _split_csv(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_database_url() -> str:
    default_db = Path(__file__).resolve().parents[3] / "vf_admin" / "manager_api.db"
    return f"sqlite:///{default_db.as_posix()}"


def _default_jwt_secret() -> str:
    try:
        from config.env import JwtConfig

        return JwtConfig.jwt_secret_key
    except Exception:
        return "change-me"


def _default_jwt_algorithm() -> str:
    try:
        from config.env import JwtConfig

        return JwtConfig.jwt_algorithm
    except Exception:
        return "HS256"


class Settings(BaseModel):
    app_name: str = Field(default_factory=lambda: os.getenv("MANAGER_API_APP_NAME", "manager-api-fastapi"))
    app_mount_path: str = Field(default_factory=lambda: os.getenv("MANAGER_API_XIAOZHI_PREFIX", "/xiaozhi"))
    manager_api_mount_prefix: str = Field(
        default_factory=lambda: os.getenv("MANAGER_API_MOUNT_PREFIX", "/manager-api")
    )
    ruoyi_api_prefix: str = Field(default_factory=lambda: os.getenv("MANAGER_API_RUOYI_PREFIX", ""))

    database_url: str = Field(default_factory=lambda: os.getenv("MANAGER_API_DATABASE_URL", _default_database_url()))
    jwt_secret: str = Field(default_factory=lambda: os.getenv("MANAGER_API_JWT_SECRET", _default_jwt_secret()))
    jwt_algorithm: str = Field(default_factory=lambda: os.getenv("MANAGER_API_JWT_ALGORITHM", _default_jwt_algorithm()))
    jwt_expire_seconds: int = Field(
        default_factory=lambda: int(os.getenv("MANAGER_API_JWT_EXPIRE_SECONDS", "43200"))
    )
    server_secret: str = Field(default_factory=lambda: os.getenv("MANAGER_API_SERVER_SECRET", "manager-api-secret"))
    cors_origins: List[str] = Field(default_factory=lambda: _split_csv(os.getenv("MANAGER_API_CORS_ORIGINS", "*")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
