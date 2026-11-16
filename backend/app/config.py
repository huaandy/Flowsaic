"""Settings, read from backend/.env. Secrets live only there (AGENTS.md ground rule 2)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Keep secret values out of validation error messages.
        hide_input_in_errors=True,
    )

    database_url: str

    # Only needed by the embedding and search scripts, so the API starts without it.
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 768


@lru_cache
def get_settings() -> Settings:
    return Settings()
