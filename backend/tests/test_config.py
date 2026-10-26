import pytest
from pydantic import ValidationError

from app.config import Settings


def test_secret_values_are_hidden_when_printed():
    settings = Settings()
    assert "test-only-secret" not in str(settings)
    assert "test-only-secret" not in repr(settings.secret_key)


def test_short_secret_key_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "too-short")
    with pytest.raises(ValidationError):
        Settings()


def test_placeholder_values_are_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "CHANGE_ME" + "x" * 40)
    with pytest.raises(ValidationError):
        Settings()


def test_missing_database_url_fails_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_validation_errors_do_not_echo_secret_values(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short-but-secret")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "short-but-secret" not in str(error.value)
