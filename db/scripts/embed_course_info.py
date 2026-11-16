"""Embed course descriptions into doc_chunks for RAG. Run after load_course_info.py.

Run from backend/:  uv run python ..\\db\\scripts\\embed_course_info.py

- One chunk per course that has a description, stored as "CODE Title: description".
- Model and dimensions come from .env (EMBEDDING_MODEL, EMBEDDING_DIM).
- Sent in batches. Each batch is saved before the next one starts, and courses whose
  chunk is already stored with the same text are skipped, so a re-run resumes.
- Retries when Gemini reports a rate limit.
- Never mix models: after changing EMBEDDING_MODEL, clear doc_chunks and embed everything again.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from google.genai import errors  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.embeddings import (  # noqa: E402
    chunk_content,
    document_prompt,
    embed_texts,
    get_client,
    is_daily_quota,
)
from app.models import Course, DocChunk  # noqa: E402

SOURCE_TYPE = "course"
BATCH_SIZE = 50


def main() -> None:
    settings = get_settings()
    client = get_client()

    with SessionLocal() as session:
        total_courses = session.scalar(select(func.count()).select_from(Course))
        courses = session.execute(
            select(Course.code, Course.title, Course.description)
            .where(Course.description.is_not(None), func.btrim(Course.description) != "")
            .order_by(Course.code)
        ).all()
        stored = dict(
            session.execute(
                select(DocChunk.source_code, DocChunk.content).where(
                    DocChunk.source_type == SOURCE_TYPE, DocChunk.chunk_index == 0
                )
            ).all()
        )

    todo = [
        course
        for course in courses
        if stored.get(course.code) != chunk_content(course.code, course.title, course.description)
    ]
    print(f"Model: {settings.embedding_model} at {settings.embedding_dim} dimensions")
    print(f"Courses in the table:           {total_courses}")
    print(f"  with a description:           {len(courses)}")
    print(f"  no description, skipped:      {total_courses - len(courses)}")
    print(f"  already embedded, skipped:    {len(courses) - len(todo)}")
    print(f"  to embed now:                 {len(todo)}")

    done = 0
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        try:
            vectors = embed_texts(
                client,
                [document_prompt(course.code, course.title, course.description) for course in batch],
            )
        except errors.APIError as error:
            if is_daily_quota(error):
                print("Stopped: the Gemini daily embedding limit is used up (free tier: 1,000 texts a day).")
                print("It resets at midnight Pacific time. Run the script again after that to resume.")
            else:
                message = (error.message or "").splitlines()[0][:200]
                print(f"Stopped: Gemini returned {error.code} {error.status}. {message}")
                print("Run the script again to resume.")
            print(f"Embedded {done} of {len(todo)} this run.")
            sys.exit(1)

        statement = insert(DocChunk)
        statement = statement.on_conflict_do_update(
            index_elements=[DocChunk.source_type, DocChunk.source_code, DocChunk.chunk_index],
            set_={
                "content": statement.excluded.content,
                "embedding": statement.excluded.embedding,
                "created_at": func.now(),
            },
        )
        with SessionLocal.begin() as session:
            session.execute(
                statement,
                [
                    {
                        "source_type": SOURCE_TYPE,
                        "source_code": course.code,
                        "chunk_index": 0,
                        "content": chunk_content(course.code, course.title, course.description),
                        "embedding": vector,
                    }
                    for course, vector in zip(batch, vectors, strict=True)
                ],
            )
        done += len(batch)
        print(f"  embedded {done} / {len(todo)}  (through {batch[-1].code})")

    with SessionLocal() as session:
        total_chunks = session.scalar(
            select(func.count()).select_from(DocChunk).where(DocChunk.source_type == SOURCE_TYPE)
        )
    print(f"Embedded this run:              {done}")
    print(f"Total course chunks in doc_chunks: {total_chunks}")


if __name__ == "__main__":
    main()
