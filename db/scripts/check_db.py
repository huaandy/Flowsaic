"""Check the database connection and make sure the pgvector extension is enabled.

Run from backend/:  uv run python ..\\db\\scripts\\check_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402


def main() -> None:
    url = engine.url
    # Never print the password.
    print(f"Connecting to {url.host}:{url.port}/{url.database} as {url.username} ...")

    with engine.begin() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        vector_version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
        distance = conn.execute(text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector")).scalar_one()

    print("Connected:", version.split(",")[0])
    print("pgvector extension enabled, version", vector_version)
    print("Cosine distance test ([1,0,0] vs [0,1,0]):", distance)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # First line only: SQLAlchemy errors can carry connection details further down.
        print("Database check FAILED:", type(exc).__name__, "-", str(exc).splitlines()[0])
        sys.exit(1)
