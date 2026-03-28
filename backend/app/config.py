from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "大家来投票"
    database_url: str = "sqlite:///./data/app.db"

    @field_validator("database_url")
    @classmethod
    def require_sync_sqlalchemy_url(cls, v: str) -> str:
        """本项目使用同步 Engine + pymysql；勿使用 asyncmy/aiomysql URL。"""
        lower = v.lower()
        if "asyncmy" in lower or "+aiomysql" in lower or "mysql+async" in lower:
            raise ValueError(
                "DATABASE_URL 请使用同步驱动，例如 mysql+pymysql://user:pass@host:3306/dbname"
            )
        return v
    jwt_secret: str = "change-me-in-production-use-openssl-rand"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    assist_cap_per_user: int = 500
    # 助力阶段结束后等待该秒数，用于客户端批量提交 assist_commit（与广播的 grace_ms 一致）
    assist_grace_seconds: float = 1.0

    # 管理控制台登录（务必在生产环境修改）
    admin_console_username: str = "admin"
    admin_console_password: str = "admin"


settings = Settings()
