"""Flow (the AI advisor), AI suggest and saving schedules. Gemini is mocked with scripted
responses; there are no real API calls and no database."""

import uuid
from datetime import time

import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types

from app import advisor
from app.advisor import AdvisorData, AdvisorTools, build_student_record, run_flow
from app.checker import SectionInfo, StudentContext
from app.progress import Offering, PlanGroup, Taken, build_progress

TERM_ID = uuid.uuid4()


def section(code, number="001", days="MW", start=(10, 0), end=(10, 50), credits=3, enrolled=5, capacity=30):
    return SectionInfo(id=uuid.uuid4(), code=code, section_number=number, title=f"{code} title", credits=credits,
                       days=days, start=time(*start) if start else None, end=time(*end) if end else None,
                       instructor="Pat Doe", enrolled=enrolled, capacity=capacity, term_id=TERM_ID)


SECTIONS = {
    "CSCI 4203": [section("CSCI 4203", days="MW", start=(14, 10), end=(15, 30))],
    "MATH 3043": [section("MATH 3043", "001", days="MWF", start=(10, 0), end=(10, 50), enrolled=23, capacity=20),
                  section("MATH 3043", "002", days="MW", start=(14, 10), end=(15, 30))],
    "CSCI 4353": [section("CSCI 4353", days="TR", start=(11, 0), end=(12, 20))],
}
GROUPS = [
    PlanGroup("cs", None, "Computer Science (12 hours)", "all", None,
              "3 hours of upper-level Computer Science electives", ["CSCI 4203", "CSCI 3103"]),
    PlanGroup("math", None, "Math choice", "choose_hours", 3, None, ["MATH 3043"]),
]


def make_data(searched=None):
    progress = build_progress(
        source="degree_plan", plan={"name": "Computer Science, BS", "catalog_year": "2026-2027"},
        term={"id": TERM_ID, "name": "Spring 2027"}, groups=GROUPS, audit_requirements=[],
        taken=[Taken("CSCI 3103", "completed", "A", 3), Taken("MATH 1023", "in_progress")], titles={}, credits={},
        offered={code: Offering(len(s), 10) for code, s in SECTIONS.items()}, prereqs={}, total_hours=120,
    )
    context = StudentContext({"CSCI 3103": 3.0}, {"MATH 1023": 3.0}, {"CSCI 4932": [["CSCI 4922"]]}, None)

    def search(query, codes):
        if searched is not None:
            searched.append((query, codes))
        return [{"code": "CSCI 4353", "title": "Deep Learning", "credits": 3.0, "description": "Neural nets", "distance": 0.2}]

    return AdvisorData(
        first_name="Alex", classification="Junior", progress=progress, context=context, term_name="Spring 2027",
        load_sections=lambda codes: {c: SECTIONS[c] for c in codes if c in SECTIONS},
        course_details=lambda code: {"title": "Deep Learning", "credits": 3.0, "description": "Neural nets",
                                     "other_requirements": None} if code.startswith("CSCI") else None,
        search=search, offered_codes=set(SECTIONS),
    )


# --- scripted Gemini --------------------------------------------------------------------------

def call_response(*calls):
    parts = [types.Part.from_function_call(name=name, args=args) for name, args in calls]
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])


def text_response(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))])


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def generate_content(self, model, contents, config):
        self.requests.append({"model": model, "contents": list(contents), "config": config})
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def all_text(request) -> str:
    """Everything sent to Gemini in one request, as text."""
    chunks = [request["config"].system_instruction or ""]
    for content in request["contents"]:
        for part in content.parts:
            chunks.append(part.text or "")
            if part.function_response is not None:
                chunks.append(str(part.function_response.response))
    return "\n".join(chunks)


# --- the student record -----------------------------------------------------------------------

def test_record_has_the_facts_and_only_the_first_name():
    record = build_student_record(make_data())
    assert "Computer Science, BS (2026-2027 catalog" in record and "Classification: Junior" in record
    assert "Passed: CSCI 3103" in record and "In progress now: MATH 1023" in record
    assert "[required] CSCI 4203" in record and "[choice] MATH 3043" in record
    assert "[elective] CSCI 4353" in record
    assert "First name: Alex" in record  # Victor's decision, Nov 18: the first name only
    assert "@" not in record and "Rivera" not in record


# --- tools ------------------------------------------------------------------------------------

def test_tools():
    searched = []
    tools = AdvisorTools(make_data(searched))
    result = tools.call("find_courses", {"query": "machine learning"})
    assert searched == [("machine learning", ["CSCI 4203", "MATH 3043", "CSCI 4353"])]  # only courses they can take
    assert result["results"][0]["can_take"] is True

    sections = tools.call("get_sections", {"codes": ["csci 4203", "ZOO 9999"]})["courses"]
    assert sections[0]["sections"][0] == {"label": "CSCI 4203-001", "title": "CSCI 4203 title", "credits": 3,
                                         "meets": "MW 14:10-15:30", "instructor": "Pat Doe", "open_seats": 25, "capacity": 30}
    assert sections[1]["sections"] == "not offered this term"

    checked = tools.call("check_schedule", {"sections": ["CSCI 4203-001", "MATH 3043-002"]})
    assert checked["conflicts"] == [{"code": "time_overlap", "message": "CSCI 4203 and MATH 3043 overlap on MW 14:10"}]
    assert tools.call("check_schedule", {"sections": ["CSCI 4203-009"]}) == {"error": "CSCI 4203-009 isn't offered this term"}
    assert "error" in tools.call("check_schedule", {"sections": ["not a label"]})

    found = tools.call("find_schedules", {"must": ["CSCI 4203", "MATH 3043"], "days_off": "F"})
    assert found["options"] == [] and found["message"] == "no combination fits without a time overlap"
    found = tools.call("find_schedules", {"must": ["CSCI 4203"], "optional": ["CSCI 4353"], "min_credits": 6})
    assert [s["label"] for s in found["options"][0]["sections"]] == ["CSCI 4203-001", "CSCI 4353-001"]
    assert "error" in tools.call("find_schedules", {"must": ["CSCI 4203"], "earliest_start": "9am"})

    course = tools.call("get_course", {"code": "CSCI 4353"})
    assert course["status_for_student"] == "can take this term" and course["counts_toward"]
    assert tools.call("get_course", {"code": "ZOO 1003"}) == {"error": "ZOO 1003 isn't in the SAU catalog"}
    assert tools.call("get_my_progress", {"group": "math"})["requirements"][0]["name"] == "Math choice"
    assert tools.call("nope", {}) == {"error": "unknown tool nope"}


def test_get_course_shows_the_whole_sequence():
    # Looking up an old or wrong code still shows the sequence, and which part is actually offered.
    data = make_data()
    data.offered_codes = data.offered_codes | {"CSCI 4932"}
    data.related_courses = lambda code, title: [
        {"code": "CSCI 4922", "title": "Senior Project I"}, {"code": "CSCI 4923", "title": "Senior Project"},
        {"code": "CSCI 4932", "title": "Senior Project II"}]
    result = AdvisorTools(data).call("get_course", {"code": "CSCI 4923"})
    assert result["status_for_student"] == "not offered this term"
    assert result["related_courses"] == [
        {"code": "CSCI 4922", "title": "Senior Project I", "offered_this_term": False,
         "status_for_student": "not offered this term"},
        {"code": "CSCI 4932", "title": "Senior Project II", "offered_this_term": True,
         "status_for_student": "offered this term, but blocked: needs CSCI 4922"},
    ]


def test_propose_runs_the_checker_and_caps_cards():
    tools = AdvisorTools(make_data())
    result = tools.call("propose_schedule", {"name": "Plan A", "sections": ["MATH 3043-001"], "explanation": "why"})
    assert result == {"shown_to_student": True, "conflicts": [],
                      "warnings": [{"code": "section_full", "message": "MATH 3043-001 is full (23/20 enrolled)"}]}
    for _ in range(2):
        tools.call("propose_schedule", {"name": "x", "sections": ["CSCI 4203-001"], "explanation": ""})
    assert tools.call("propose_schedule", {"name": "x", "sections": ["CSCI 4203-001"]}) == {"error": "at most 3 schedules per reply"}
    assert len(tools.proposals) == 3


# --- the loop ---------------------------------------------------------------------------------

def test_flow_uses_tools_then_answers_with_the_first_name_only():
    client = FakeClient([
        call_response(("find_schedules", {"must": ["CSCI 4203"], "optional": ["CSCI 4353"], "min_credits": 6})),
        call_response(("propose_schedule", {"name": "Spring plan", "sections": ["CSCI 4203-001", "CSCI 4353-001"],
                                             "explanation": "Required course plus an elective you liked."})),
        text_response("Hi {first_name}! Here's a 6-credit start: CSCI 4203 plus CSCI 4353."),
    ])
    history = [{"role": "user", "text": "I like AI."}, {"role": "assistant", "text": "Nice, {first_name}."}]
    result = run_flow(make_data(), "Build me a schedule", history, client=client, model="test-model")

    assert result["reply"] == "Hi Alex! Here's a 6-credit start: CSCI 4203 plus CSCI 4353."
    assert result["memory"].startswith("Hi {first_name}!")
    assert "[Schedules shown: Spring plan: CSCI 4203-001, CSCI 4353-001]" in result["memory"]
    assert result["tools_used"] == ["find_schedules", "propose_schedule"]
    [proposal] = result["proposals"]
    assert proposal["credits"] == 6 and proposal["conflicts"] == [] and proposal["warnings"] == []

    requests = client.models.requests
    assert len(requests) == 3 and all(r["model"] == "test-model" for r in requests)
    assert [c.role for c in requests[0]["contents"]] == ["user", "model", "user"]  # history, then the message
    assert [c.role for c in requests[2]["contents"]][-2:] == ["model", "user"]  # tool results go back as "user"
    assert requests[1]["contents"][-1].parts[0].function_response.name == "find_schedules"
    assert requests[0]["config"].automatic_function_calling.disable is True
    for request in requests:
        # Privacy: the first name goes to Gemini (Nov 18); no last name, email or ID.
        assert "First name: Alex" in all_text(request)
        assert "Rivera" not in all_text(request) and "@demo" not in all_text(request)


def test_flow_stops_after_max_steps_with_a_text_answer():
    responses = [call_response(("get_my_progress", {}))] * (advisor.MAX_STEPS - 1) + [text_response("Done.")]
    client = FakeClient(responses)
    result = run_flow(make_data(), "hi", [], client=client, model="m")
    assert result["reply"] == "Done."
    assert client.models.requests[-1]["config"].tools is None  # the last call can't use tools
    # Two tool steps before the end, Flow is told to wrap up and propose.
    assert advisor.WRAP_UP in all_text(client.models.requests[advisor.MAX_STEPS - 2])
    assert advisor.WRAP_UP not in all_text(client.models.requests[advisor.MAX_STEPS - 3])


def test_an_empty_answer_gets_one_retry():
    client = FakeClient([text_response(""), text_response("Here's what I found.")])
    result = run_flow(make_data(), "hi", [], client=client, model="m")
    assert result["reply"] == "Here's what I found."
    assert advisor.ANSWER_NOW in all_text(client.models.requests[1])


def test_gemini_errors_become_ai_unavailable():
    class Broken:
        class models:
            @staticmethod
            def generate_content(**kwargs):
                raise errors.APIError(500, {"error": {"message": "boom"}})

    with pytest.raises(advisor.AdvisorUnavailable) as raised:
        run_flow(make_data(), "hi", [], client=Broken(), model="m")
    assert raised.value.code == "ai_unavailable"


# --- endpoints --------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    from app import auth
    from app.main import app
    from app.routers import auth as auth_router

    student_id = uuid.uuid4()
    monkeypatch.setattr(auth, "find_student_id", lambda email: student_id)
    monkeypatch.setattr(auth_router, "load_profile", lambda sid: {
        "id": sid, "name": "Alex Rivera", "email": "a@demo.flowsaic.test", "classification": None, "major": None,
        "catalog_year": None, "degree_plan": None, "has_hold": False, "total_hours_earned": None,
        "total_hours_needed": None, "audit_refreshed_at": None, "connected_mysau": False})
    from app.routers import ai, planning
    # Nothing saved on /me/preferences: suggest uses the form alone.
    monkeypatch.setattr(ai, "load_saved_preferences", lambda sid: dict(planning.DEFAULT_PREFERENCES))
    test_client = TestClient(app)
    test_client.student_id = student_id
    return test_client


def fake_result():
    sections = [SECTIONS["CSCI 4203"][0], SECTIONS["MATH 3043"][0]]
    return {"reply": "Hi Alex!", "memory": "Hi {first_name}!", "tools_used": ["propose_schedule"],
            "proposals": [{"name": "Plan", "explanation": "because", "sections": sections, "credits": 6.0,
                           "conflicts": [], "warnings": [{"code": "section_full", "section_ids": [sections[1].id],
                                                          "message": "MATH 3043-001 is full (23/20 enrolled)"}]}]}


def test_advisor_endpoint(client, monkeypatch):
    calls = []
    monkeypatch.setattr(advisor, "advise", lambda sid, message, history: calls.append((sid, message, history)) or fake_result())
    assert client.post("/ai/advisor", json={"message": "hi"}).json() == {"error": "not_authenticated"}
    client.post("/auth/login", json={"email": "1"})
    body = client.post("/ai/advisor", json={"message": "hi", "history": [{"role": "assistant", "text": "Hello"}]}).json()
    assert body["reply"] == "Hi Alex!" and body["memory"] == "Hi {first_name}!"
    [proposal] = body["proposals"]
    assert proposal["term_id"] == str(TERM_ID) and len(proposal["section_ids"]) == 2
    assert proposal["sections"][0]["start_time"] == "14:10"
    assert calls == [(client.student_id, "hi", [{"role": "assistant", "text": "Hello"}])]
    assert client.post("/ai/advisor", json={"message": ""}).json() == {"error": "invalid_request"}


@pytest.mark.parametrize(("code", "status"), [("gemini_model_not_set", 503), ("ai_unavailable", 502)])
def test_advisor_endpoint_errors(client, monkeypatch, code, status):
    def fail(*args):
        raise advisor.AdvisorUnavailable(code)

    monkeypatch.setattr(advisor, "advise", fail)
    client.post("/auth/login", json={"email": "1"})
    response = client.post("/ai/advisor", json={"message": "hi"})
    assert response.status_code == status and response.json() == {"error": code}


def test_suggest_endpoint(client, monkeypatch):
    from app import suggest as suggest_engine
    from app.routers import ai

    calls = []
    sections = [SECTIONS["CSCI 4203"][0], SECTIONS["MATH 3043"][0]]
    warning = {"code": "section_full", "section_ids": [sections[1].id], "message": "MATH 3043-001 is full (23/20 enrolled)"}
    monkeypatch.setattr(ai, "run_suggest", lambda sid, request: calls.append(request)
                        or suggest_engine.Suggestion(sections, [], [warning], "because"))
    client.post("/auth/login", json={"email": "1"})
    body = client.post("/ai/suggest", json={"target_credits": 15, "unavailable": [{"days": "MWF", "start": "13:00", "end": "17:00"}],
                                            "preferred_time": "morning", "notes": "I like databases"}).json()
    assert body["explanation"] == "because" and len(body["section_ids"]) == 2
    assert body["sections"][0]["start_time"] == "14:10"
    assert body["warnings"][0]["code"] == "section_full" and body["conflicts"] == []
    [request] = calls
    assert request.target_credits == 15 and request.preferred_time == "morning" and request.notes == "I like databases"
    assert [(b.days, f"{b.start:%H:%M}", f"{b.end:%H:%M}") for b in request.unavailable] == [("MWF", "13:00", "17:00")]
    assert request.request_text == ("Build my schedule for next term. Target: 15 credits. I can't do MWF 13:00-17:00. "
                                    "Keep my fixed calendar commitments free. I prefer morning classes. Notes: I like databases")
    assert ai.preferences_message(ai.Preferences()) == ("Build my schedule for next term. "
                                                         "Keep my fixed calendar commitments free.")


def test_save_schedule_flow(client, monkeypatch):
    from app.routers import schedules

    saved = {}
    monkeypatch.setattr(schedules, "run_check", lambda sid, ids, term: {"conflicts": [], "warnings": []})
    monkeypatch.setattr(schedules, "save_schedule", lambda sid, body, schedule_id: saved.update(body=body) or uuid.UUID(int=7))
    monkeypatch.setattr(schedules, "get_schedule", lambda sid, schedule_id: {
        "id": schedule_id, "name": saved["body"].name, "term": {"id": TERM_ID, "name": "Spring 2027"},
        "source": saved["body"].source, "created_at": "2026-11-17T12:00:00Z", "credits": 3.0, "section_count": 1,
        "sections": [], "conflicts": [], "warnings": []})
    client.post("/auth/login", json={"email": "1"})
    body = {"name": "Plan A", "term_id": str(TERM_ID), "section_ids": [str(uuid.uuid4())], "source": "ai"}
    response = client.post("/schedules", json=body)
    assert response.status_code == 201 and response.json()["source"] == "ai" and response.json()["name"] == "Plan A"

    conflict = {"code": "time_overlap", "section_ids": [uuid.UUID(int=1)], "message": "A and B overlap on MW 10:00"}
    monkeypatch.setattr(schedules, "run_check", lambda sid, ids, term: {"conflicts": [conflict], "warnings": []})
    response = client.post("/schedules", json=body)
    assert response.status_code == 422
    assert response.json() == {"error": "schedule_has_conflicts", "conflicts": [
        {"code": "time_overlap", "section_ids": [str(uuid.UUID(int=1))], "message": "A and B overlap on MW 10:00",
         "event_ids": []}]}
    assert client.post("/schedules", json={**body, "section_ids": []}).json() == {"error": "invalid_request"}
    assert client.post("/schedules", json={**body, "source": "robot"}).json() == {"error": "invalid_request"}


def test_schedule_ownership_errors(client, monkeypatch):
    from app.auth import ApiError
    from app.routers import schedules

    def missing(*args):
        raise ApiError(404, "schedule_not_found")

    monkeypatch.setattr(schedules, "get_schedule", missing)
    monkeypatch.setattr(schedules, "delete_schedule", missing)
    monkeypatch.setattr(schedules, "owns_schedule", lambda sid, schedule_id: False)
    client.post("/auth/login", json={"email": "1"})
    other = str(uuid.uuid4())
    assert client.get(f"/schedules/{other}").json() == {"error": "schedule_not_found"}
    assert client.delete(f"/schedules/{other}").status_code == 404
    body = {"name": "x", "term_id": str(TERM_ID), "section_ids": [str(uuid.uuid4())]}
    assert client.put(f"/schedules/{other}", json=body).json() == {"error": "schedule_not_found"}
