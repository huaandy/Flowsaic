"""Gemini embeddings for RAG. Shared by the embed script, the search script and (later) AI suggest.

Two things are specific to gemini-embedding-2 (Google's embeddings docs, checked Nov 16):
- A plain list of strings in one request is combined into ONE embedding. To get one
  embedding per text, each text must be its own Content object.
- The task_type setting is not supported. The task goes in the text instead:
  documents as "title: ... | text: ...", queries as "task: search result | query: ...".
  Documents and queries must always use these same formats, or search quality drops.

Only course text and the search query are sent. Never student names, emails or IDs.
"""

import time
from collections.abc import Callable

from google import genai
from google.genai import errors, types

from app.config import get_settings
from app.models import EMBEDDING_DIM

RETRY_CODES = {429, 500, 502, 503, 504}  # rate limit or a temporary server problem
# Seconds to wait before each retry. The free tier allows roughly 100 texts a minute and
# sometimes needs several minutes to clear, so the later waits are long.
RETRY_WAITS = [15, 30, 60, 60, 60, 120, 120, 120]


def chunk_content(code: str, title: str, description: str) -> str:
    """The chunk stored in doc_chunks.content: 'CSCI 3103 Data Structures: <description>'."""
    return f"{code} {title}: {description}"


def document_prompt(code: str, title: str, description: str) -> str:
    """The same chunk in the format gemini-embedding-2 expects for a document."""
    return f"title: {code} {title} | text: {description}"


def query_prompt(query: str) -> str:
    """A search query in the format gemini-embedding-2 expects for retrieval."""
    return f"task: search result | query: {query}"


def get_client() -> genai.Client:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in backend/.env")
    if settings.embedding_dim != EMBEDDING_DIM:
        raise RuntimeError(
            f"EMBEDDING_DIM is {settings.embedding_dim} but doc_chunks.embedding is "
            f"vector({EMBEDDING_DIM}). Changing it needs a migration and a full re-embed."
        )
    return genai.Client(api_key=settings.gemini_api_key)


def is_daily_quota(error: errors.APIError) -> bool:
    """True when a 429 is the per-day quota. Waiting a minute won't help, so don't retry.

    On the free tier gemini-embedding-2 allows 1,000 texts a day (each text counts as one).
    """
    details = error.details if isinstance(error.details, dict) else {}
    for item in details.get("error", {}).get("details", []):
        for violation in item.get("violations", []):
            if "PerDay" in violation.get("quotaId", ""):
                return True
    return False


def embed_texts(
    client: genai.Client,
    texts: list[str],
    *,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> list[list[float]]:
    """Embed each text separately in one request. Retries on rate limits and server errors."""
    settings = get_settings()
    contents = [types.Content(parts=[types.Part.from_text(text=text)]) for text in texts]
    config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)

    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            response = client.models.embed_content(
                model=settings.embedding_model, contents=contents, config=config
            )
            break
        except errors.APIError as error:
            out_of_retries = attempt == len(RETRY_WAITS)
            if error.code not in RETRY_CODES or out_of_retries or is_daily_quota(error):
                raise
            wait = RETRY_WAITS[attempt]
            log(f"  Gemini returned {error.code} {error.status}; waiting {wait}s (retry {attempt + 1} of {len(RETRY_WAITS)})")
            sleep(wait)

    vectors = [list(embedding.values) for embedding in response.embeddings or []]
    if len(vectors) != len(texts):
        raise RuntimeError(f"sent {len(texts)} texts but got {len(vectors)} embeddings back")
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise RuntimeError(f"expected {EMBEDDING_DIM} dimensions, got {len(vector)}")
    return vectors
