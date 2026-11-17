"""Database engine and sessions. Creating the engine does not open a connection."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# The engine is the shared connection to Postgres. Everything uses this one.
engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    # Fail with a clear error after 10 seconds instead of hanging if the database is unreachable.
    connect_args={"connect_timeout": 10},
)
# A session is one unit of work: open it, read or write, then close it.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session
