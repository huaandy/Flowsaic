"""Database connection. No tables yet: models are added once the schema is agreed.

The engine is created lazily (on first use), so importing the app or running
tests that don't touch the database never opens a connection.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Every SQLAlchemy model inherits from this. Alembic reads Base.metadata."""


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url.get_secret_value()
    # pool_pre_ping: check a pooled connection is still alive before using it.
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed afterwards."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
