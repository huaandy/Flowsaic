"""App settings, read from environment variables (or a local .env file).

Every secret and environment-specific value lives here, in one place.
Nothing secret is ever hard-coded. See .env.example for the variable names.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"

    # SecretStr hides the value when printed or logged ("**********"),
    # so a stray print(settings) can't leak the password or key.
    database_url: SecretStr
    secret_key: SecretStr = Field(min_length=32)

    @field_validator("database_url", "secret_key")
    @classmethod
    def reject_placeholders(cls, value: SecretStr) -> SecretStr:
        # Refuse to start with the placeholder values copied from .env.example.
        if "CHANGE_ME" in value.get_secret_value():
            raise ValueError("still set to the .env.example placeholder; set a real value")
        return value


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them. Fails at startup if a required value is missing."""
    return Settings()
