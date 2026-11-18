"""Embed course descriptions into doc_chunks for RAG, re-embedding only what changed.

Used by db/scripts/embed_course_info.py and by the public data refresh.
- One chunk per course that has a description, stored as "CODE Title: description".
- doc_chunks.content_hash is the sha256 of that chunk. A course is embedded only when its
  hash differs from the stored one (new course or changed text), so re-runs cost nothing.
- Sent in batches; each batch is saved before the next, so a stopped run resumes.
- Never mix models: after changing EMBEDDING_MODEL, clear doc_chunks and embed everything again.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from google.genai import errors
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.embeddings import chunk_content, document_prompt, embed_texts, get_client, is_daily_quota
from app.models import Course, DocChunk

SOURCE_TYPE = "course"
BATCH_SIZE = 50


def content_hash(text: str) -> str:
    """Matches the migration's backfill: encode(sha256(convert_to(content, 'UTF8')), 'hex')."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class EmbedResult:
    total_courses: int = 0
    with_description: int = 0
    todo: int = 0
    embedded: int = 0
    total_chunks: int = 0
    stopped: str | None = None  # why the run stopped early, or None


def embed_changed_courses(log: Callable[[str], None] = lambda _message: None) -> EmbedResult:
    result = EmbedResult()
    with SessionLocal() as session:
        result.total_courses = session.scalar(select(func.count()).select_from(Course))
        courses = session.execute(
            select(Course.code, Course.title, Course.description)
            .where(Course.description.is_not(None), func.btrim(Course.description) != "")
            .order_by(Course.code)
        ).all()
        stored = dict(
            session.execute(
                select(DocChunk.source_code, DocChunk.content_hash).where(
                    DocChunk.source_type == SOURCE_TYPE, DocChunk.chunk_index == 0
                )
            ).all()
        )

    todo = []
    for course in courses:
        content = chunk_content(course.code, course.title, course.description)
        if stored.get(course.code) != content_hash(content):
            todo.append((course, content))
    result.with_description = len(courses)
    result.todo = len(todo)
    if not todo:
        result.total_chunks = len(stored)
        return result

    client = get_client()  # only needs GEMINI_API_KEY when something changed
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        try:
            vectors = embed_texts(
                client,
                [document_prompt(course.code, course.title, course.description) for course, _ in batch],
            )
        except errors.APIError as error:
            if is_daily_quota(error):
                result.stopped = "Gemini daily embedding limit used up; resets at midnight Pacific"
            else:
                result.stopped = f"Gemini returned {error.code} {error.status}"
            break

        statement = insert(DocChunk)
        statement = statement.on_conflict_do_update(
            index_elements=[DocChunk.source_type, DocChunk.source_code, DocChunk.chunk_index],
            set_={
                "content": statement.excluded.content,
                "content_hash": statement.excluded.content_hash,
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
                        "content": content,
                        "content_hash": content_hash(content),
                        "embedding": vector,
                    }
                    for (course, content), vector in zip(batch, vectors, strict=True)
                ],
            )
        result.embedded += len(batch)
        log(f"  embedded {result.embedded} / {len(todo)}  (through {batch[-1][0].code})")

    with SessionLocal() as session:
        result.total_chunks = session.scalar(
            select(func.count()).select_from(DocChunk).where(DocChunk.source_type == SOURCE_TYPE)
        )
    return result
