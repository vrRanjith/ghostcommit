from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # protected_namespaces: let us use a "model_name" field without Pydantic warning.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    # Public base URL of the app; GitHub redirects back here after login.
    app_url: str = "http://localhost:5173"

    database_url: str
    session_secret: str
    token_encryption_key: str

    github_client_id: str = ""
    github_client_secret: str = ""

    backboard_api_key: str = ""
    backboard_base_url: str = "https://app.backboard.io/api"
    # Open-weight model served through Backboard (challenge requires open-source AI).
    llm_provider: str = "openrouter"
    model_name: str = "meta-llama/llama-3.3-70b-instruct"

    # Email: Resend in production, SMTP (Mailpit) locally.
    resend_api_key: str = ""
    email_from: str = "GhostCommit <ghost@buildloop.tech>"
    smtp_host: str = ""
    smtp_port: int = 1025

    stall_days: int = 7

    @field_validator("session_secret")
    @classmethod
    def strong_session_secret(cls, v: str) -> str:
        # A short secret lets attackers brute-force cookie signatures and forge sessions.
        if len(v) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")
        return v

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, v: str) -> str:
        # Render hands out postgres:// URLs; SQLAlchemy async needs the asyncpg driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
