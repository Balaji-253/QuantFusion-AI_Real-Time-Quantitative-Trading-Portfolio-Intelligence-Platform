from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QuantFusion AI"
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./quantfusion.db"

    enable_simulator: bool = True
    simulator_interval_seconds: float = Field(default=1.0, gt=0, le=60)

    max_order_notional: float = Field(default=10_000.0, gt=0)
    max_position_quantity: int = Field(default=100, gt=0)
    initial_cash: float = Field(default=100_000.0, ge=0)

    admin_api_token: str = Field(default="", repr=False)

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value == "/":
            raise ValueError("api_prefix must start with '/' and cannot be '/'")
        return value.rstrip("/")

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
