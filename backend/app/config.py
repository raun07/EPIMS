"""
Application configuration via pydantic-settings.
All values can be overridden by environment variables or a .env file.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, EmailStr, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    APP_NAME: str = "EPIMS"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ── Security ────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="change-me-in-production-use-openssl-rand-hex-32",
        description="HS256 JWT signing key — must be >= 32 chars in production",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "epims"
    POSTGRES_PASSWORD: str = "epims_dev_password"
    POSTGRES_DB: str = "epims"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:  # noqa: N802
        """Used by Alembic (sync driver)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_CACHE_DB: int = 1
    CACHE_TTL_SECONDS: int = 300  # 5 minutes default

    @property
    def REDIS_URL(self) -> str:  # noqa: N802
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def REDIS_CACHE_URL(self) -> str:  # noqa: N802
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CACHE_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CACHE_DB}"

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev server
    ]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

    # ── Email ─────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    EMAIL_FROM: EmailStr = "noreply@epims.local"
    EMAIL_FROM_NAME: str = "EPIMS System"

    # ── Object Storage (MinIO / S3) ───────────────────────────────────────────
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "epims-documents"
    S3_REGION: str = "us-east-1"

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Pagination ───────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ── Business Rules ────────────────────────────────────────────────────────
    DEFAULT_CURRENCY: str = "INR"
    INVOICE_TOLERANCE_PCT: float = 2.0  # 3-way match tolerance
    PR_NUMBER_PREFIX: str = "PR"
    PO_NUMBER_PREFIX: str = "PO"
    GRN_NUMBER_PREFIX: str = "GRN"
    INV_NUMBER_PREFIX: str = "INV"
    MAT_NUMBER_PREFIX: str = "MAT"
    VEN_NUMBER_PREFIX: str = "VEN"
    MOV_NUMBER_PREFIX: str = "MOV"
    APPROVAL_TIMEOUT_HOURS: int = 48

    # ── Superuser (seeded on first startup) ──────────────────────────────────
    FIRST_SUPERUSER_EMAIL: str = "admin@epims.local"
    FIRST_SUPERUSER_PASSWORD: str = "Admin@123456"
    FIRST_SUPERUSER_NAME: str = "System Administrator"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
