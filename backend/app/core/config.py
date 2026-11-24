"""
app/core/config.py
Application configuration via pydantic-settings.
All values can be overridden by a .env file or real environment variables.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Central settings object – loaded once at import time."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Security
    # ------------------------------------------------------------------ #
    SECRET_KEY: str = "change-this-to-a-long-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "sqlite+aiosqlite:///./health_monitor.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: object) -> str:
        """
        Normalize DATABASE_URL for dual SQLite/PostgreSQL async compatibility:
        - Expands relative sqlite paths to absolute file paths under BACKEND_DIR.
        - Translates postgres:// or postgresql:// to postgresql+asyncpg:// for async SQLAlchemy.
        """
        if not isinstance(v, str):
            return str(v)
        url = v.strip()
        if url.startswith("sqlite+aiosqlite:///./"):
            rel = url[len("sqlite+aiosqlite:///./"):]
            abs_path = (BACKEND_DIR / rel).resolve().as_posix()
            return f"sqlite+aiosqlite:///{abs_path}"
        # Cloud providers (Render, Heroku, Neon, Supabase) often provide postgres:// or postgresql://
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]

        if "postgresql+asyncpg://" in url:
            import re
            url = url.replace("sslmode=", "ssl=")
            url = re.sub(r"[?&]channel_binding=[^&]+", "", url)
        return url

    # ------------------------------------------------------------------ #
    # Device authentication
    # ------------------------------------------------------------------ #
    DEVICE_API_KEY_HEADER: str = "X-Device-API-Key"

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    CORS_ORIGINS: List[str] | str = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> List[str]:
        """Accept a JSON list, comma-separated string, or Python list."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # Admin bootstrap
    # ------------------------------------------------------------------ #
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-this-password"

    # ------------------------------------------------------------------ #
    # Business rules
    # ------------------------------------------------------------------ #
    STALE_READING_THRESHOLD_MINUTES: int = 60
    MAX_ECG_SAMPLES_PER_BATCH: int = 10_000

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    APP_VERSION: str = "1.0.0"


# Singleton – import this everywhere instead of instantiating Settings again.
settings = Settings()
