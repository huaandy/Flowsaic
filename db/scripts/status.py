"""Print what's loaded in the local database, one `name=count` per line. Used by setup.ps1.

Run from backend/:  uv run python ..\\db\\scripts\\status.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Course, DegreePlan, DocChunk, Section, Student  # noqa: E402


def main() -> None:
    with SessionLocal() as session:
        counts = {
            "sections": session.scalar(select(func.count()).select_from(Section).where(Section.active.is_(True))),
            "courses": session.scalar(select(func.count()).select_from(Course)),
            "embedded": session.scalar(select(func.count()).select_from(DocChunk)),
            "degree_plans": session.scalar(select(func.count()).select_from(DegreePlan)),
            "students": session.scalar(select(func.count()).select_from(Student)),
        }
    for name, count in counts.items():
        print(f"{name}={count}")


if __name__ == "__main__":
    main()
