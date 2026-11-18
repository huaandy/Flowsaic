"""The catalog (GET /terms, /courses, /courses/{id}), the per-course flags from app/progress.py,
CORS, and the header search (GET /search). Storage is faked; no database, no Gemini."""

import uuid
from datetime import time

import pytest
from fastapi.testclient import TestClient

from app import course_search, progress
from app.config import load_settings
from app.progress import Offering, PlanGroup, Taken, course_flags
from app.routers import catalog

TERM = {"id": uuid.uuid4(), "code": "2026-2027 - Spring", "name": "Spring 2027", "is_current_registration": True}

# A made-up plan: Core lists ZOO 2103 and ZOO 3103 (needs ZOO 2103); an elective line covers
# upper-level Zoology; ART 1103 is on no requirement.
GROUPS = [
    PlanGroup("core", None, "Core (6 hours)", "all", None, None, ["ZOO 2103", "ZOO 3103"]),
    PlanGroup("elec", None, "Electives (6 hours)", "all", None, "6 hours of upper-level Zoology electives", []),
]


@pytest.fixture(autouse=True)
def zoology_subject(monkeypatch):
    monkeypatch.setitem(progress.SUBJECT_PREFIXES, "zoology", ("ZOO",))


def inputs(taken, source="degree_plan", audit=None):
    return dict(
        source=source, plan={"name": "Zoology, BS", "catalog_year": "2026-2027"} if source == "degree_plan" else None,
        term={"id": TERM["id"], "name": "Spring 2027"}, groups=GROUPS if source == "degree_plan" else [],
        audit_requirements=audit or [], taken=taken, titles={}, credits={},
        offered={"ZOO 3103": Offering(1, 5), "ZOO 4103": Offering(1, 5), "ART 1103": Offering(1, 5)},
        prereqs={"ZOO 3103": [["ZOO 2103"]], "ZOO 4103": [["ZOO 3103", "ZOO 3203"]]}, total_hours=120,
    )


def student_flags():
    """Built inside a test (after zoology_subject), so the elective line parses."""
    return course_flags(inputs([Taken("ZOO 2103", "completed", "B", 3), Taken("ART 1013", "in_progress"),
                                Taken("ZOO 1001", "completed", "F", 1)]))


# --- flags (pure) ---------------------------------------------------------------------------------

def test_eligibility_matches_progress_rules():
    FLAGS = student_flags()
    assert FLAGS.eligibility("ZOO 2103") == "completed"
    assert FLAGS.eligibility("ART 1013") == "in_progress"
    assert FLAGS.eligibility("ZOO 1001") == "eligible"  # an F isn't completed
    assert FLAGS.eligibility("ZOO 3103") == "eligible"  # its prereq is passed
    assert FLAGS.eligibility("ZOO 4103") == "missing_prereq"
    assert FLAGS.missing_prereqs("ZOO 4103") == [["ZOO 3103", "ZOO 3203"]]


def test_in_progress_counts_for_prereqs():
    flags = course_flags(inputs([Taken("ZOO 3103", "in_progress")]))
    assert flags.eligibility("ZOO 4103") == "eligible"


def test_plan_membership_and_requirement_names():
    FLAGS = student_flags()
    assert FLAGS.for_course("ZOO 3103") == {"eligibility": "eligible", "missing_prereqs": [], "on_my_plan": True,
                                            "requirement_names": ["Core (6 hours)"]}
    # Not listed by name, but an upper-level Zoology course fills the elective line.
    assert FLAGS.requirement_names("ZOO 4103") == ["6 hours of upper-level Zoology electives"]
    # A course the plan lists by name is never also an elective.
    assert FLAGS.requirement_names("ZOO 3103") == ["Core (6 hours)"]
    assert FLAGS.for_course("ART 1103")["on_my_plan"] is False


def test_audit_students_use_their_audit_options():
    audit = [{"name": "Major Core", "parent_name": None, "status": "not_met", "rule": "all", "hours_earned": 3,
              "hours_required": 6, "course_options": ["ZOO 3103"], "note": None}]
    flags = course_flags(inputs([], source="audit", audit=audit))
    assert flags.requirement_names("ZOO 3103") == ["Major Core"]
    assert flags.for_course("ZOO 4103")["on_my_plan"] is False  # no elective parsing for audits


def test_level_and_delivery():
    assert progress.course_level("CSCI 3103") * 1000 == 3000
    assert catalog.delivery_for("MW", time(9), time(10), "Main Campus") == "in_person"
    assert catalog.delivery_for(None, None, None, "Main Campus") == "online"  # TBA
    assert catalog.delivery_for("MW", time(9), time(10), "High School Online") == "online"
    assert catalog.delivery_for("MW", None, None, "Online") == "online"


# --- endpoints --------------------------------------------------------------------------------------

def sec(number, days="MW", start="09:00", end="09:50", enrolled=5, capacity=20, location="Main Campus", active=True):
    online = not (days and start) or "online" in location.lower()
    return {"id": uuid.uuid4(), "section_number": number, "instructor": "Pat Doe", "location": location,
            "building": "Science", "room": "101", "days": days, "start_time": start, "end_time": end,
            "division": "UG", "enrolled": enrolled, "capacity": capacity, "seats_open": max(capacity - enrolled, 0),
            "active": active, "delivery": "online" if online else "in_person"}


def course_row(code, title, sections, department="Dept of Zoology", credits=3):
    return {"id": uuid.uuid4(), "code": code, "title": title, "department": department, "credits": credits,
            "description": f"{title} description", "other_requirements": None, "sections": sections}


ROWS = [
    course_row("ART 1103", "Art Appreciation", [sec("001", days=None, start=None, end=None, location="Online")],
               department="Dept of Art"),
    course_row("ZOO 3103", "Animal Behavior", [sec("001", days="TR", start="11:00", end="12:15", enrolled=20)]),
    course_row("ZOO 4103", "Field Zoology", [sec("001", days="MWF"), sec("002", days="MW", enrolled=0)], credits=4),
]


@pytest.fixture
def client(monkeypatch):
    from app import auth
    from app.routers import auth as auth_router

    student_id = uuid.uuid4()
    monkeypatch.setattr(auth, "find_student_id", lambda email: student_id)
    monkeypatch.setattr(auth_router, "load_profile", lambda sid: {
        "id": sid, "name": "Alex Rivera", "email": "a@demo.flowsaic.test", "classification": None, "major": None,
        "catalog_year": None, "degree_plan": None, "has_hold": False, "total_hours_earned": None,
        "total_hours_needed": None, "audit_refreshed_at": None, "connected_mysau": False})
    calls = {}

    def term_catalog(term_id, search, department):
        calls["catalog"] = (term_id, search, department)
        rows = [dict(r, sections=list(r["sections"])) for r in ROWS
                if department in (None, r["department"])]
        return rows, sorted({r["department"] for r in ROWS})

    monkeypatch.setattr(catalog, "find_term", lambda term_id: TERM if term_id in (None, TERM["id"]) else None)
    monkeypatch.setattr(catalog, "list_terms", lambda: [TERM])
    monkeypatch.setattr(catalog, "load_term_catalog", term_catalog)
    flags = student_flags()
    monkeypatch.setattr(catalog, "load_flags", lambda sid: flags)
    monkeypatch.setattr(catalog, "load_course", lambda course_id, term_id: (
        {k: v for k, v in ROWS[2].items() if k != "sections"}, ROWS[2]["sections"] + [sec("003", active=False)])
        if course_id == ROWS[2]["id"] else None)
    from app.main import app

    test_client = TestClient(app)
    test_client.calls = calls
    test_client.post("/auth/login", json={"email": "1"})
    return test_client


def test_catalog_needs_a_session():
    from app.main import app

    anonymous = TestClient(app)
    for path in ("/terms", f"/courses?term_id={TERM['id']}", f"/courses/{uuid.uuid4()}", "/search?q=zoo"):
        response = anonymous.get(path)
        assert response.status_code == 401 and response.json() == {"error": "not_authenticated"}, path


def test_terms(client):
    assert client.get("/terms").json() == [{**TERM, "id": str(TERM["id"])}]


def test_courses_with_flags_and_sections(client):
    body = client.get("/courses", params={"term_id": str(TERM["id"]), "search": " behavior "}).json()
    assert client.calls["catalog"] == (TERM["id"], "behavior", None)
    assert body["total"] == 3 and body["departments"] == ["Dept of Art", "Dept of Zoology"]
    zoo = next(c for c in body["courses"] if c["code"] == "ZOO 3103")
    assert zoo["level"] == 3000 and zoo["eligibility"] == "eligible" and zoo["on_my_plan"] is True
    assert zoo["requirement_names"] == ["Core (6 hours)"] and zoo["prereqs"] == [["ZOO 2103"]]
    assert zoo["offered"] is True and zoo["seats_open"] == 0
    [section] = zoo["sections"]
    assert section["days"] == "TR" and section["start_time"] == "11:00" and section["seats_open"] == 0
    assert section["delivery"] == "in_person" and section["active"] is True
    art = next(c for c in body["courses"] if c["code"] == "ART 1103")
    assert art["sections"][0]["delivery"] == "online" and art["eligibility"] == "eligible"


@pytest.mark.parametrize(("params", "codes"), [
    ({"on_my_plan": True}, ["ZOO 3103", "ZOO 4103"]),
    ({"eligible_only": True}, ["ART 1103", "ZOO 3103"]),
    ({"level": 4000}, ["ZOO 4103"]),
    ({"delivery": "online"}, ["ART 1103"]),
    ({"delivery": "in_person"}, ["ZOO 3103", "ZOO 4103"]),
    ({"open_only": True}, ["ART 1103", "ZOO 4103"]),
    ({"credits": 4}, ["ZOO 4103"]),
    ({"days": "fwm"}, ["ZOO 4103"]),
    ({"department": "Dept of Art"}, ["ART 1103"]),
])
def test_course_filters(client, params, codes):
    body = client.get("/courses", params={"term_id": str(TERM["id"]), **params}).json()
    assert [c["code"] for c in body["courses"]] == codes and body["total"] == len(codes)


def test_courses_paging(client):
    body = client.get("/courses", params={"term_id": str(TERM["id"]), "limit": 1, "offset": 1}).json()
    assert body["total"] == 3 and [c["code"] for c in body["courses"]] == ["ZOO 3103"]


@pytest.mark.parametrize("params", [{}, {"term_id": "nope"}, {"limit": 0}, {"limit": 101}, {"offset": -1},
                                    {"level": 99}, {"delivery": "hybrid"}, {"days": "XYZ"}])
def test_courses_rejects_bad_queries(client, params):
    query = {"term_id": str(TERM["id"]), **params} if "term_id" not in params and params else params
    response = client.get("/courses", params=query)
    assert response.status_code == 422 and response.json() == {"error": "invalid_request"}


def test_unknown_term(client):
    response = client.get("/courses", params={"term_id": str(uuid.uuid4())})
    assert response.status_code == 404 and response.json() == {"error": "term_not_found"}


def test_course_detail(client):
    body = client.get(f"/courses/{ROWS[2]['id']}").json()
    assert body["code"] == "ZOO 4103" and body["term"]["name"] == "Spring 2027"
    assert body["eligibility"] == "missing_prereq" and body["missing_prereqs"] == [["ZOO 3103", "ZOO 3203"]]
    assert [s["active"] for s in body["sections"]] == [True, True, False]  # inactive sections show, marked
    assert body["seats_open"] == 35  # 15 + 20: active sections only
    response = client.get(f"/courses/{uuid.uuid4()}")
    assert response.status_code == 404 and response.json() == {"error": "course_not_found"}
    response = client.get(f"/courses/{ROWS[2]['id']}", params={"term_id": str(uuid.uuid4())})
    assert response.json() == {"error": "term_not_found"}


# --- CORS ---------------------------------------------------------------------------------------------

def test_cors_defaults_to_the_vite_dev_server(tmp_path):
    settings = load_settings(env_files=(tmp_path / "missing.env",))
    assert settings.cors_origins == ["http://localhost:8443", "http://127.0.0.1:8443"]


def test_cors_never_allows_everyone(monkeypatch, tmp_path):
    monkeypatch.setenv("FRONTEND_ORIGINS", "*, http://localhost:5173/")
    assert load_settings(env_files=(tmp_path / "missing.env",)).cors_origins == ["http://localhost:5173"]


def test_cors_headers():
    from app.main import app

    client = TestClient(app)
    preflight = {"Access-Control-Request-Method": "GET"}
    allowed = client.options("/terms", headers={"Origin": "http://localhost:8443", **preflight})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8443"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    other = client.options("/terms", headers={"Origin": "http://evil.test", **preflight})
    assert "access-control-allow-origin" not in other.headers


# --- header search ------------------------------------------------------------------------------------

@pytest.fixture
def search_client(client, monkeypatch):
    ids = {code: uuid.uuid4() for code in ("ZOO 3103", "ZOO 4103", "ART 1103", "BIOL 1003")}
    monkeypatch.setattr(course_search, "offered_codes", lambda term_id: {"ZOO 3103", "ZOO 4103", "ART 1103"})
    monkeypatch.setattr(course_search, "text_matches", lambda query, limit: [
        {"course_id": ids["ZOO 3103"], "code": "ZOO 3103", "title": "Animal Behavior",
         "description": "How animals act. " * 20, "match_type": "title"}][:limit])
    monkeypatch.setattr(course_search, "course_ids", lambda codes: {c: (ids[c], "desc") for c in codes if c in ids})
    client.rag_calls = []

    def described_like(query, k):
        client.rag_calls.append((query, k))
        return [("ZOO 3103", "Animal Behavior", "dup"), ("BIOL 1003", "Biology", "Cells and life"),
                ("ZOO 4103", "Field Zoology", "Out in the field")]

    monkeypatch.setattr(catalog, "described_like", described_like)
    return client


def test_search_puts_text_matches_first_then_rag(search_client):
    body = search_client.get("/search", params={"q": "animal   behavior"}).json()
    assert body["query"] == "animal behavior"
    assert [(r["code"], r["match_type"], r["offered"]) for r in body["results"]] == [
        ("ZOO 3103", "title", True), ("BIOL 1003", "description", False), ("ZOO 4103", "description", True)]
    assert body["results"][0]["snippet"].endswith("…") and len(body["results"][0]["snippet"]) < 200
    assert body["results"][1]["snippet"] == "Cells and life"
    assert set(body["results"][0]) == {"course_id", "code", "title", "snippet", "match_type", "offered"}


def test_search_skips_rag_when_text_fills_the_limit(search_client):
    body = search_client.get("/search", params={"q": "behavior", "limit": 1}).json()
    assert [r["code"] for r in body["results"]] == ["ZOO 3103"] and search_client.rag_calls == []


@pytest.mark.parametrize("q", ["a", " a ", "x" * 101])
def test_search_needs_two_characters(search_client, q):
    response = search_client.get("/search", params={"q": q})
    assert response.status_code == 422 and response.json() == {"error": "invalid_request"}


def test_rag_failure_still_returns_text_matches(client, monkeypatch):
    def broken(query, k):
        raise RuntimeError("GEMINI_API_KEY is not set")

    catalog._described_like.cache_clear()
    monkeypatch.setattr(catalog, "_described_like", broken)
    assert catalog.described_like("animals", 5) == []


def test_code_queries():
    assert course_search.code_pattern("csci3103") == "CSCI 3103%"
    assert course_search.code_pattern("CSCI 31") == "CSCI 31%"
    assert course_search.code_pattern("zoo") == "ZOO %"
    assert course_search.code_pattern("animal behavior") is None
    assert course_search.snippet("Short text.") == "Short text."
    assert course_search.snippet(None) is None
    long = "Intro words. " * 30 + "The genetics part. " + "More. " * 30
    assert "genetics" in course_search.snippet(long, "genetics")
