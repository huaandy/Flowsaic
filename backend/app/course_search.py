"""Course search, shared by Flow (find_courses), the header search (GET /search) and the
catalog: RAG over course descriptions, plus plain code/title matching.

RAG is for unstructured text only (AGENTS.md): it ranks descriptions by meaning. Everything
structured (sections, prereqs, eligibility) still comes from SQL.
"""

import re

from google import genai
from sqlalchemy import case, or_, select

from app.db import SessionLocal
from app.embeddings import embed_texts, query_prompt
from app.models import Course, DocChunk, Section

CODE_QUERY_RE = re.compile(r"^\s*([A-Za-z]{2,5})\s*(\d{0,4})\s*$")


def search_courses(client: genai.Client, query: str, codes: list[str] | None, k: int = 8) -> list[dict]:
    """RAG: the k course descriptions closest in meaning to the query, among `codes` (None = all)."""
    vector = embed_texts(client, [query_prompt(query)])[0]
    distance = DocChunk.embedding.cosine_distance(vector).label("distance")
    statement = (
        select(Course.code, Course.title, Course.credits, Course.description, distance)
        .join(Course, Course.code == DocChunk.source_code)
        .where(DocChunk.source_type == "course")
        .order_by(distance).limit(k)
    )
    if codes is not None:
        statement = statement.where(DocChunk.source_code.in_(codes))
    with SessionLocal() as session:
        rows = session.execute(statement).all()
    return [{"code": code, "title": title, "credits": float(credits) if credits is not None else None,
             "description": (description or "")[:400], "distance": round(float(dist), 3)}
            for code, title, credits, description, dist in rows]


def code_pattern(query: str) -> str | None:
    """'csci3103' / 'CSCI 31' -> 'CSCI 31%' (course codes are 'PREFIX 1234'). None if it isn't code-like."""
    match = CODE_QUERY_RE.match(query)
    if not match:
        return None
    prefix, number = match[1].upper(), match[2]
    return f"{prefix} {number}%" if number else f"{prefix} %"


def text_match_filter(query: str):
    """SQL filter: the code or title contains the query (a code typed without its space counts)."""
    conditions = [Course.code.icontains(query, autoescape=True), Course.title.icontains(query, autoescape=True)]
    pattern = code_pattern(query)
    if pattern:
        conditions.append(Course.code.like(pattern))
    return or_(*conditions)


def text_matches(query: str, limit: int) -> list[dict]:
    """Courses whose code or title matches, best first: code match, then title starting with it,
    then the rest; ties by code."""
    pattern = code_pattern(query)
    rank = case(
        (Course.code.like(pattern) if pattern else Course.code.ilike(query), 0),
        (Course.title.istartswith(query, autoescape=True), 1),
        else_=2,
    )
    with SessionLocal() as session:
        rows = session.execute(
            select(Course.id, Course.code, Course.title, Course.description, rank.label("rank"))
            .where(text_match_filter(query)).order_by(rank, Course.code).limit(limit)
        ).all()
    return [{"course_id": cid, "code": code, "title": title, "description": description,
             "match_type": "code" if r == 0 else "title"} for cid, code, title, description, r in rows]


def course_ids(codes: list[str]) -> dict[str, tuple]:
    """code -> (id, description) for the given codes."""
    if not codes:
        return {}
    with SessionLocal() as session:
        return {code: (cid, description) for cid, code, description in session.execute(
            select(Course.id, Course.code, Course.description).where(Course.code.in_(codes)))}


def offered_codes(term_id) -> set[str]:
    """Course codes with an active section in the term (for the search results' `offered`)."""
    if term_id is None:
        return set()
    with SessionLocal() as session:
        return set(session.scalars(
            select(Course.code).join(Section, Section.course_id == Course.id)
            .where(Section.term_id == term_id, Section.active.is_(True)).distinct()))


def snippet(text: str | None, query: str = "", width: int = 160) -> str | None:
    """A short piece of the description, around the first query word found if any."""
    if not text:
        return None
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    lowered = text.lower()
    hits = [lowered.find(word) for word in query.lower().split() if len(word) > 2 and word in lowered]
    start = max(min(hits) - 40, 0) if hits else 0
    piece = text[start:start + width].strip()
    return ("…" if start else "") + piece + "…"
