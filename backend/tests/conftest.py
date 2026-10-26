import os

# Fake, test-only settings, set before the app is imported.
# Not secrets: they only exist inside the test run.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/flowsaic_test")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-anywhere-else")

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_settings():
    """Clear cached settings around each test so env changes in one test can't leak into another."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
