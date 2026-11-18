"""Embed course descriptions into doc_chunks for RAG. Run after load_course_info.py.

Run from backend/:  uv run python ..\\db\\scripts\\embed_course_info.py

- One chunk per course that has a description, stored as "CODE Title: description".
- Model and dimensions come from .env (EMBEDDING_MODEL, EMBEDDING_DIM).
- Only courses whose text changed are embedded (doc_chunks.content_hash), so a re-run
  resumes and an unchanged catalog costs nothing.
- Retries when Gemini reports a rate limit.
- Never mix models: after changing EMBEDDING_MODEL, clear doc_chunks and embed everything again.
The work is done by backend/app/course_embed.py, shared with the public data refresh.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import get_settings  # noqa: E402
from app.course_embed import embed_changed_courses  # noqa: E402


def main() -> None:
    settings = get_settings()
    print(f"Model: {settings.embedding_model} at {settings.embedding_dim} dimensions")
    result = embed_changed_courses(log=print)
    print(f"Courses in the table:           {result.total_courses}")
    print(f"  with a description:           {result.with_description}")
    print(f"  no description, skipped:      {result.total_courses - result.with_description}")
    print(f"  unchanged, skipped:           {result.with_description - result.todo}")
    print(f"  needed embedding:             {result.todo}")
    print(f"Embedded this run:              {result.embedded}")
    print(f"Total course chunks in doc_chunks: {result.total_chunks}")
    if result.stopped:
        print(f"Stopped early: {result.stopped}. Run the script again to resume.")
        sys.exit(1)


if __name__ == "__main__":
    main()
