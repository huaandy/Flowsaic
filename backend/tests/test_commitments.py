"""Calendar commitments block courses everywhere the checker runs: the checker codes
commitment_overlap (fixed, a conflict) and commitment_overlap_flexible (a warning), the solver,
Flow's tools and record, and AI suggest's saved preferences. No database, no Gemini."""

import uuid
from datetime import time

import pytest

from app import solver
from app.advisor import AdvisorTools, build_student_record, preference_line
from app.checker import Commitment, check_schedule
from app.routers import ai, planning
from tests.test_advisor import SECTIONS, make_data
from tests.test_checker import codes, section, student


def commitment(day="M", start=(9, 0), end=(12, 0), fixed=True, category="work"):
    return Commitment(uuid.uuid4(), day, time(*start), time(*end), category, fixed)


def with_commitments(*items, **kwargs):
    context = student(**kwargs)
    context.commitments = list(items)
    return context


# --- the checker ------------------------------------------------------------------------------------

def test_fixed_commitment_is_a_conflict():
    work = commitment("M", (9, 0), (12, 0))
    course = section("CSCI 3103", days="MWF", start=(10, 0), end=(10, 50))
    result = check_schedule([course], with_commitments(work))
    assert codes(result, "conflicts") == ["commitment_overlap"]
    [item] = result["conflicts"]
    assert item["section_ids"] == [course.id] and item["event_ids"] == [work.id]
    assert item["message"] == "CSCI 3103-001 meets during your work commitment (M 09:00-12:00)"


def test_flexible_commitment_is_a_warning():
    gym = commitment("W", (10, 30), (11, 30), fixed=False, category="personal_study")
    result = check_schedule([section("CSCI 3103", days="MWF", start=(10, 0), end=(10, 50))], with_commitments(gym))
    assert result["conflicts"] == [] and codes(result, "warnings") == ["commitment_overlap_flexible"]
    assert result["warnings"][0]["message"] == ("CSCI 3103-001 overlaps your flexible personal/study commitment "
                                                "(W 10:30-11:30)")


@pytest.mark.parametrize(("days", "start", "end", "overlaps"), [
    ("MWF", (10, 0), (10, 50), True),
    ("TR", (10, 0), (10, 50), False),   # another day
    ("MW", (12, 0), (12, 50), False),   # starts as the event ends
    ("MW", (8, 0), (9, 0), False),      # ends as the event starts
    ("MW", (8, 30), (9, 30), True),
    (None, None, None, False),          # online/TBA never overlaps
])
def test_commitment_overlap_rule(days, start, end, overlaps):
    result = check_schedule([section("CSCI 3103", days=days, start=start, end=end)], with_commitments(commitment()))
    assert (codes(result, "conflicts") == ["commitment_overlap"]) is overlaps


def test_one_item_per_section_and_event():
    a, b = commitment("M", (9, 0), (10, 0)), commitment("W", (9, 0), (10, 0), fixed=False)
    result = check_schedule([section("CSCI 3103", days="MW", start=(9, 30), end=(10, 20)),
                             section("MATH 2753", days="MW", start=(9, 0), end=(9, 50))], with_commitments(a, b))
    assert len(result["conflicts"]) == 2 + 1  # 2 sections x fixed event, plus their own time_overlap
    assert codes(result, "conflicts").count("time_overlap") == 1
    assert codes(result, "warnings") == ["commitment_overlap_flexible", "commitment_overlap_flexible"]


def test_messages_never_include_the_event_title():
    result = check_schedule([section("CSCI 3103")], with_commitments(commitment("M", (10, 0), (11, 0))))
    # Commitment has no title field at all: the checker can't leak it to Gemini.
    assert not hasattr(Commitment, "title")
    assert "work commitment" in result["conflicts"][0]["message"]


def test_save_returns_commitment_conflicts_with_event_ids(monkeypatch):
    from tests.test_advisor import TERM_ID
    from tests.test_planning import signed_in
    from app.routers import schedules

    event_id = uuid.uuid4()
    conflict = {"code": "commitment_overlap", "section_ids": [uuid.UUID(int=1)],
                "message": "CSCI 3103-001 meets during your work commitment (M 09:00-12:00)", "event_ids": [event_id]}
    monkeypatch.setattr(schedules, "run_check", lambda sid, ids, term: {"conflicts": [conflict], "warnings": []})
    client = signed_in(monkeypatch, uuid.uuid4())
    body = {"name": "Plan A", "term_id": str(TERM_ID), "section_ids": [str(uuid.uuid4())]}
    response = client.post("/schedules", json=body)
    assert response.status_code == 422
    assert response.json()["conflicts"][0]["event_ids"] == [str(event_id)]
    checked = client.post("/schedules/check", json={"term_id": str(TERM_ID), "section_ids": body["section_ids"]}).json()
    assert checked["conflicts"][0]["code"] == "commitment_overlap"


# --- the solver -------------------------------------------------------------------------------------

def test_commitment_blocks_split_fixed_and_flexible():
    hard, soft = solver.commitment_blocks([commitment("M"), commitment("T", fixed=False)])
    assert [b.days for b in hard] == ["M"] and [b.days for b in soft] == ["T"]


def test_solver_ranks_midday_preferred_days_and_flexible_events():
    early = section("CSCI 3103", "001", days="TR", start=(8, 0), end=(9, 15))
    noon = section("CSCI 3103", "002", days="MW", start=(11, 30), end=(12, 45))
    by_course = {"CSCI 3103": [early, noon]}
    best = lambda c: solver.search(["CSCI 3103"], [], by_course, c)["schedules"][0]["sections"][0]  # noqa: E731
    assert best(solver.Constraints(preferred_time="midday")) is noon
    assert best(solver.Constraints(preferred_days="TR")) is early
    gym = solver.Block("MW", time(11, 0), time(12, 0))
    assert best(solver.Constraints(preferred_time="midday", flexible_blocks=[gym])) is early


# --- Flow -------------------------------------------------------------------------------------------

def test_flow_never_schedules_over_a_fixed_commitment():
    data = make_data()
    # CSCI 4203's only section meets MW 14:10. A fixed shift then makes it unschedulable.
    data.context.commitments = [commitment("W", (14, 0), (17, 0))]
    result = AdvisorTools(data).call("find_schedules", {"must": ["CSCI 4203"]})
    assert result["options"] == [] and "unavailable" in result["unschedulable"][0]["reason"]
    # MATH 3043 has a MWF 10:00 section and a MW 14:10 one: only the first fits.
    result = AdvisorTools(data).call("find_schedules", {"must": ["MATH 3043"]})
    assert [o["sections"][0]["label"] for o in result["options"]] == ["MATH 3043-001"]


def test_flow_proposals_show_commitment_conflicts():
    data = make_data()
    data.context.commitments = [commitment("M", (14, 0), (15, 0))]
    tools = AdvisorTools(data)
    result = tools.call("propose_schedule", {"name": "Plan", "sections": ["CSCI 4203-001"], "explanation": "x"})
    assert [c["code"] for c in result["conflicts"]] == ["commitment_overlap"]
    assert tools.proposals[0]["conflicts"][0]["event_ids"]


def test_record_lists_commitments_and_preferences_without_titles():
    data = make_data()
    data.context.commitments = [commitment("T", (15, 0), (18, 0)), commitment("M", (11, 30), (12, 30), fixed=False,
                                                                                category="extracurricular")]
    data.preferences = {**planning.DEFAULT_PREFERENCES, "preferred_time": "midday", "preferred_days": "MTWR",
                        "min_credits": 12, "max_credits": 16, "delivery": ["in_person"], "flexibility": "strict",
                        "updated_at": "2026-11-18T12:00:00Z"}
    record = build_student_record(data)
    assert "- flexible extracurricular: M 11:30-12:30" in record
    assert "- fixed work: T 15:00-18:00" in record
    assert record.index("M 11:30") < record.index("T 15:00")  # by day
    assert ("Saved scheduling preferences (flexibility: strict): 12-16 credits; midday classes; prefers days MTWR; "
            "in-person sections only") in record
    assert "Calendar commitments: none" in build_student_record(make_data())
    assert preference_line(None) == preference_line(dict(planning.DEFAULT_PREFERENCES)) == \
        "Saved scheduling preferences: none saved"


# --- AI suggest -------------------------------------------------------------------------------------

SAVED = {**planning.DEFAULT_PREFERENCES, "preferred_time": "midday", "preferred_days": "MW", "min_credits": 12,
         "max_credits": 15, "delivery": ["in_person"], "flexibility": "strict", "updated_at": "2026-11-18T12:00:00Z"}


def test_saved_preferences_are_the_default():
    merged, flexibility = ai.with_saved(ai.Preferences(), SAVED)
    assert (merged.preferred_time, merged.preferred_days, merged.min_credits, merged.max_credits, merged.delivery) == \
        ("midday", "MW", 12, 15, ["in_person"])
    assert flexibility == "strict"
    assert ai.preferences_message(merged, flexibility) == (
        "Build my schedule for next term. I want 12-15 credits. Keep my fixed calendar commitments free. "
        "I prefer midday classes. I prefer classes on MW. In-person sections only. Treat these preferences as firm.")


def test_the_request_body_overrides_saved_preferences():
    body = ai.Preferences.model_validate({"preferred_time": "evening", "delivery": ["online"], "min_credits": 16})
    merged, _ = ai.with_saved(body, SAVED)
    assert (merged.preferred_time, merged.delivery, merged.preferred_days) == ("evening", ["online"], "MW")
    assert merged.min_credits == 15  # never above the saved maximum
    assert "Online sections only." in ai.preferences_message(merged)


def test_a_saved_minimum_of_zero_means_no_minimum():
    # Nov 20: new and returning students start at 0 = no minimum. Auto-generate keeps its usual
    # target instead of building a one-course schedule, and the request says "Up to 18 credits".
    from app.suggest import SuggestRequest, constraints_for

    saved = {**SAVED, "min_credits": 0, "max_credits": 18}
    merged, _ = ai.with_saved(ai.Preferences(), saved)
    assert (merged.min_credits, merged.max_credits) == (None, 18)
    assert "Up to 18 credits." in ai.preferences_message(merged)
    c = constraints_for(SuggestRequest(min_credits=merged.min_credits, max_credits=merged.max_credits), [])
    assert (c.min_credits, c.max_credits) == (12, 18)
    # A minimum typed into the form still wins.
    merged, _ = ai.with_saved(ai.Preferences.model_validate({"min_credits": 9}), saved)
    assert merged.min_credits == 9
    # Flow's record says it in words.
    assert "no minimum, up to 18 credits" in preference_line(saved)


def test_nothing_saved_means_the_form_alone():
    body = ai.Preferences(target_credits=15)
    merged, flexibility = ai.with_saved(body, dict(planning.DEFAULT_PREFERENCES))
    assert merged == body and flexibility is None


def test_suggest_endpoint_uses_saved_preferences(monkeypatch):
    from app import suggest as suggest_engine
    from tests.test_planning import signed_in

    calls = []
    monkeypatch.setattr(ai, "run_suggest", lambda sid, request: calls.append(request)
                        or suggest_engine.Suggestion([], [], [], "nothing fits"))
    monkeypatch.setattr(ai, "load_saved_preferences", lambda sid: SAVED)
    client = signed_in(monkeypatch, uuid.uuid4())
    response = client.post("/ai/suggest", json={"preferred_time": "morning"})
    assert response.status_code == 200 and response.json()["section_ids"] == []
    [request] = calls
    assert request.preferred_time == "morning"  # the form wins
    assert (request.preferred_days, request.delivery, request.min_credits, request.max_credits) == ("MW", ["in_person"], 12, 15)
    assert "I prefer morning classes. I prefer classes on MW." in request.request_text
    for bad in ({"preferred_time": "noon"}, {"delivery": ["hybrid"]}, {"preferred_days": "XYZ"}, {"max_credits": 30}):
        assert client.post("/ai/suggest", json=bad).json() == {"error": "invalid_request"}


def test_sections_fixture_is_unchanged():
    # The shared Flow fixtures these tests build on.
    assert [s.days for s in SECTIONS["MATH 3043"]] == ["MWF", "MW"]
