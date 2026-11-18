"""Where settings come from: backend/.env or the repo root, with a clear error when missing."""

import pytest

from app.config import MissingSettings, load_settings


@pytest.fixture(autouse=True)
def no_env_var(monkeypatch):
    # conftest.py sets DATABASE_URL for the other tests; these tests read files only.
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_a_root_env_file_works(tmp_path):
    root = tmp_path / "root.env"
    root.write_text("DATABASE_URL=postgresql+psycopg://a:b@localhost:5433/root\n", encoding="utf-8")
    settings = load_settings((root, tmp_path / "missing-backend.env"))
    assert settings.database_url.endswith("/root")


def test_backend_env_wins_over_root(tmp_path):
    root = tmp_path / "root.env"
    backend = tmp_path / "backend.env"
    root.write_text("DATABASE_URL=postgresql+psycopg://a:b@localhost:5433/root\nGEMINI_MODEL=root-model\n", encoding="utf-8")
    backend.write_text("DATABASE_URL=postgresql+psycopg://a:b@localhost:5433/backend\n", encoding="utf-8")
    settings = load_settings((root, backend))
    assert settings.database_url.endswith("/backend")
    assert settings.gemini_model == "root-model"  # a setting only the root file has still counts


def test_missing_database_url_says_what_to_do(tmp_path):
    with pytest.raises(MissingSettings) as raised:
        load_settings((tmp_path / "nothing.env", tmp_path / "nothing-either.env"))
    message = str(raised.value)
    assert message.startswith("DATABASE_URL is missing.")
    assert "backend/.env" in message and ".env.txt" in message
