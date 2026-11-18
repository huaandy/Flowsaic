"""Settings, read from a .env file. Secrets live only there (AGENTS.md ground rule 2).

The .env can sit in backend/ (preferred) or in the repo root; if both exist, backend/.env
wins for any setting it has. Real environment variables win over both.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
# Later files win. Missing files are skipped.
ENV_FILES = (REPO_DIR / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
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

    # Public SAU catalog. catoid 10 = the 2026-27 undergraduate catalog; change it here only.
    catalog_base_url: str = "https://catalog.saumag.edu"
    catalog_catoid: int = 10
    # Never request faster than this, even if robots.txt allows it. robots.txt asks for 120 s.
    catalog_min_delay_seconds: float = 120.0
    # Refresh public data in the background on startup when the last good run is older.
    public_refresh_on_startup: bool = True
    public_refresh_max_age_days: int = 7
    # Course descriptions change once a catalog year, so by default a refresh reuses the
    # saved raw catalog text (no requests). Set true to crawl course pages again, e.g.
    # after changing catalog_catoid to a new year.
    course_info_crawl: bool = False
    # Degree maps come from SAU's main site: its program pages copy the catalog curriculum
    # and are open, while the catalog's own program pages sit behind bot protection.
    # Its robots.txt sets no crawl delay; we wait this long between pages anyway.
    saumag_base_url: str = "https://www.saumag.edu"
    degree_maps_delay_seconds: float = 30.0


class MissingSettings(RuntimeError):
    """A required setting isn't in the .env file. The message says what to do."""


def load_settings(env_files=ENV_FILES) -> Settings:
    try:
        return Settings(_env_file=env_files)
    except ValidationError as error:
        missing = [str(e["loc"][0]).upper() for e in error.errors() if e["type"] == "missing"]
        names = ", ".join(missing) or "A setting"
        raise MissingSettings(
            f"{names} is missing. Put your .env file in backend/.env (or the Flowsaic folder), "
            "starting from backend/.env.example, and check it isn't named .env.txt. "
            "setup.cmd checks all of this for you."
        ) from None


@lru_cache  # read .env once, then reuse; restart the server after changing .env
def get_settings() -> Settings:
    return load_settings()
