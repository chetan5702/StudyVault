from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StudyVault"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["development", "production", "test"] = "development"
    debug: bool = Field(default=False, validation_alias="STUDYVAULT_DEBUG")
    database_url: str = "sqlite:///./studyvault.db"
    secret_key: str = ""
    seed_demo: bool = False
    algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=60 * 24, gt=0)
    upload_dir: str = "./uploads"
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_user_storage_bytes: int = Field(default=1024 * 1024 * 1024, gt=0)
    login_max_failures: int = Field(default=5, gt=0)
    public_auth_limit_enabled: bool = True
    register_per_hour: int = Field(default=12, gt=0)
    recovery_per_hour: int = Field(default=30, gt=0)
    login_per_hour: int = Field(default=120, gt=0)
    login_failure_window_seconds: int = Field(default=15 * 60, gt=0)
    login_lockout_seconds: int = Field(default=15 * 60, gt=0)
    require_email_verification: bool = False
    public_frontend_url: str = "http://localhost:5173"
    email_verification_token_expire_minutes: int = Field(default=24 * 60, gt=0)
    password_reset_token_expire_minutes: int = Field(default=60, gt=0)
    verification_resend_cooldown_seconds: int = Field(default=60, gt=0)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    email_provider: Literal["disabled", "resend", "file"] = "disabled"
    resend_api_key: str = ""
    email_from: str = ""
    email_sink_dir: str = "./email-sink"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, populate_by_name=True)

    @model_validator(mode="after")
    def secure_configuration(self):
        if self.environment == "production":
            if not self.require_email_verification:
                raise ValueError("Production requires email verification")
            if self.email_provider != "resend" or not self.resend_api_key or not self.email_from:
                raise ValueError("Production requires a configured non-file email provider")
            frontend = urlparse(self.public_frontend_url)
            if (
                frontend.scheme != "https"
                or not frontend.hostname
                or frontend.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("Production requires a public HTTPS frontend URL")
            if (
                self.secret_key.startswith("REPLACE_")
                or len(self.secret_key) < 32
                or len(set(self.secret_key)) < 12
                or self.secret_key.startswith("dev-")
            ):
                raise ValueError(
                    "Production requires a randomly generated SECRET_KEY of at least 32 characters"
                )
            if not self.public_auth_limit_enabled:
                raise ValueError("Production requires public authentication rate limiting")
            if self.seed_demo or self.debug:
                raise ValueError("Production forbids SEED_DEMO and DEBUG")
        elif not self.secret_key:
            self.secret_key = secrets.token_urlsafe(48)
        return self

    @property
    def email_available(self) -> bool:
        return self.email_provider == "file" or (
            self.email_provider == "resend" and bool(self.resend_api_key and self.email_from)
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [entry.strip() for entry in self.cors_origins.split(",") if entry.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


class TokenData(BaseModel):
    user_id: str
    email: str
    full_name: str
    token_version: int = 0


class AuthTokenPayload(BaseModel):
    sub: str
    email: str
    full_name: str
    ver: int = 0
    exp: int | None = Field(default=None)
