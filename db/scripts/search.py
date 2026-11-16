"""Search course descriptions by meaning: the 8 most relevant courses for a plain-English query.

Run from backend/:  uv run python ..\\db\\scripts\\search.py "intro to programming"

The query is embedded with the same model as the courses (EMBEDDING_MODEL in .env), then
ranked by cosine distance using the HNSW index. Smaller distance = closer match.
Each search uses one Gemini embedding request.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from google.genai import errors  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.embeddings import embed_texts, get_client, query_prompt  # noqa: E402
from app.models import Course, DocChunk  # noqa: E402

TOP_K = 8


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        sys.exit('Usage: uv run python ..\\db\\scripts\\search.py "your query"')

    try:
        query_vector = embed_texts(get_client(), [query_prompt(query)])[0]
    except errors.APIError as error:
        sys.exit(f"Gemini returned {error.code} {error.status}. The query was not embedded.")

    distance = DocChunk.embedding.cosine_distance(query_vector).label("distance")
    with SessionLocal() as session:
        rows = session.execute(
            select(Course.code, Course.title, distance)
            .join(Course, Course.code == DocChunk.source_code)
            .where(DocChunk.source_type == "course")
            .order_by(distance)
            .limit(TOP_K)
        ).all()

    sys.stdout.reconfigure(errors="replace")  # a stray symbol in a title must not crash the print
    print(f'Top {len(rows)} courses for "{query}"')
    print(f"{'#':>2}  {'code':<10} {'distance':>8}  title")
    for rank, row in enumerate(rows, start=1):
        print(f"{rank:>2}  {row.code:<10} {row.distance:>8.4f}  {row.title}")


if __name__ == "__main__":
    main()
