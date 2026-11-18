"""Faster schedules (Nov 18): AI suggest built by code with one Gemini call to explain, and
Flow's shortcuts (propose_schedule by option number, finishing in the same response).
Gemini is mocked; no database."""

import uuid
from datetime import time

import pytest
from google.genai import errors, types

from app import suggest
from app.advisor import AdvisorTools, run_flow
from app.checker import Commitment
from app.solver import Block
from app.suggest import SuggestRequest, candidate_courses, constraints_for
from tests.test_advisor import FakeClient, call_response, make_data, text_response


def can(code, kind, group):
    return {"code": code, "kind": kind, "counts_toward": [group]}


def codes(sections):
    return sorted({s.code for s in sections})


class Broken:
    class models:
        @staticmethod
        def generate_content(**kwargs):
            raise errors.APIError(500, {"error": {"message": "boom"}})


# --- choosing courses ----------------------------------------------------------------------------

def test_candidates_required_first_and_one_per_choice_group():
    can_take = [
        can("LIT 2213", "choice", "Literature choice"), can("LIT 2223", "choice", "Literature choice"),
        can("ZOO 4103", "elective", "6 hours of upper-level Zoology electives"),
        can("ZOO 3103", "required", "Core"), can("ZOO 3203", "required", "Core"),
        can("ART 1103", "choice", "Arts choice"),
    ]
    assert candidate_courses(can_take) == ["ZOO 3103", "ZOO 3203", "ART 1103", "LIT 2213", "ZOO 4103"]


def test_notes_matches_move_up_within_their_kind():
    can_take = [can("LIT 2213", "choice", "Literature choice"), can("LIT 2223", "choice", "Literature choice"),
                can("ZOO 3103", "required", "Core")]
    # LIT 2223 matched the notes, so it's the Literature pick; required still comes first.
    assert candidate_courses(can_take, boosted=["LIT 2223"]) == ["ZOO 3103", "LIT 2223"]


def test_constraints_from_the_form():
    fixed = Commitment(uuid.uuid4(), "M", time(9), time(12), "work", True)
    flexible = Commitment(uuid.uuid4(), "T", time(9), time(10), "personal_study", False)
    c = constraints_for(SuggestRequest(delivery=["in_person"], preferred_time="none"), [fixed, flexible])
    assert (c.min_credits, c.max_credits) == (12, 15)  # the default range
    assert [b.days for b in c.unavailable] == ["M"] and [b.days for b in c.flexible_blocks] == ["T"]
    assert c.allow_online is False and c.online_only is False and c.preferred_time is None
    c = constraints_for(SuggestRequest(target_credits=15, max_credits=16, delivery=["online"]), [])
    assert (c.min_credits, c.max_credits, c.allow_online, c.online_only) == (15, 16, True, True)
    c = constraints_for(SuggestRequest(min_credits=9, max_credits=12, preferred_time="midday"), [])
    assert (c.min_credits, c.max_credits, c.preferred_time) == (9, 12, "midday")


# --- building the schedule -------------------------------------------------------------------------

def test_builds_a_schedule_without_overlaps():
    # Only 9 credits can be taken, under the 12-credit minimum: what fits is still returned.
    sections, reason = suggest.build_schedule(make_data(), SuggestRequest())
    assert reason is None
    assert codes(sections) == ["CSCI 4203", "CSCI 4353", "MATH 3043"]
    math = next(s for s in sections if s.code == "MATH 3043")
    assert math.section_number == "001"  # 002 overlaps CSCI 4203 on MW 14:10


def test_fixed_commitments_are_kept_free():
    data = make_data()
    data.context.commitments = [Commitment(uuid.uuid4(), "W", time(10), time(11), "work", True)]
    sections, _ = suggest.build_schedule(data, SuggestRequest())
    # MATH 3043-001 meets during the shift and -002 overlaps CSCI 4203, so one of those two goes.
    assert not any(s.days and "W" in s.days and s.start < time(11) and time(10) < s.end for s in sections)
    assert len({s.code for s in sections} & {"MATH 3043", "CSCI 4203"}) == 1


def test_unavailable_times_and_online_only():
    request = SuggestRequest(unavailable=[Block("TR", time(8), time(18))])
    assert "CSCI 4353" not in codes(suggest.build_schedule(make_data(), request)[0])
    sections, reason = suggest.build_schedule(make_data(), SuggestRequest(delivery=["online"]))
    assert sections == [] and reason  # every fake section meets in person


def test_nothing_to_take():
    data = make_data()
    data.progress["can_take"] = []
    result = suggest.suggest(data, SuggestRequest(), client=None, model=None)
    assert result.sections == [] and "couldn't build" in result.explanation


# --- explaining it (one Gemini call, no tools) -------------------------------------------------------

def test_one_gemini_call_explains_and_never_picks():
    client = FakeClient([text_response("Hi Alex! This keeps CSCI 4203 and your afternoons.")])
    result = suggest.suggest(make_data(), SuggestRequest(request_text="Build my schedule for next term."), client, "m")
    assert result.explanation.startswith("Hi Alex!")
    [request] = client.models.requests
    assert request["config"].tools is None  # Gemini can't change the schedule
    sent = request["contents"][0].parts[0].text
    assert "CSCI 4203-001" in sent and "Build my schedule for next term." in sent
    assert "First name: Alex" in request["config"].system_instruction
    assert codes(result.sections) == ["CSCI 4203", "CSCI 4353", "MATH 3043"]
    assert [w["code"] for w in result.warnings] == ["section_full"]  # the checker still runs


@pytest.mark.parametrize(("client", "model"), [(None, None), (Broken(), "m"), (FakeClient([text_response("")]), "m"),
                                               (FakeClient([]), None)])
def test_without_gemini_a_plain_explanation_is_used(client, model):
    result = suggest.suggest(make_data(), SuggestRequest(notes="databases"), client, model)
    assert result.sections and result.explanation.startswith("3 courses, 9 credits")
    assert "1 of them required" in result.explanation


def test_notes_use_one_description_search():
    searched = []
    data = make_data(searched)
    client = FakeClient([text_response("Done.")])
    suggest.suggest(data, SuggestRequest(notes="neural networks"), client, "m")
    assert searched == [("neural networks", ["CSCI 4203", "MATH 3043", "CSCI 4353"])]
    searched.clear()
    suggest.suggest(data, SuggestRequest(notes="  "), FakeClient([text_response("Done.")]), "m")
    assert searched == []  # no notes, no search


# --- Flow's shortcuts ---------------------------------------------------------------------------------

def test_propose_by_option_number():
    tools = AdvisorTools(make_data())
    found = tools.call("find_schedules", {"must": ["CSCI 4203"], "optional": ["CSCI 4353"], "min_credits": 6})
    assert found["options"]
    result = tools.call("propose_schedule", {"name": "Plan", "option": 1, "explanation": "x"})
    assert result["shown_to_student"] is True
    assert [s.label for s in tools.proposals[0]["sections"]] == [b["label"] for b in found["options"][0]["sections"]]
    assert "isn't in the last find_schedules result" in tools.call(
        "propose_schedule", {"name": "Plan", "option": 9, "explanation": "x"})["error"]


def test_propose_by_option_needs_a_search_first():
    error = AdvisorTools(make_data()).call("propose_schedule", {"name": "Plan", "option": 1, "explanation": "x"})
    assert "0 options" in error["error"]


def proposal_with_text(text, args):
    parts = [types.Part.from_text(text=text), types.Part.from_function_call(name="propose_schedule", args=args)]
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])


def test_flow_finishes_in_the_proposing_response():
    client = FakeClient([
        call_response(("find_schedules", {"must": ["CSCI 4203"], "optional": ["CSCI 4353"], "min_credits": 6})),
        proposal_with_text("Hi {first_name}! Option 1 fits your week.", {"name": "Plan", "option": 1, "explanation": "x"}),
    ])
    result = run_flow(make_data(), "Build me a schedule", [], client=client, model="m")
    assert len(client.models.requests) == 2  # no third round trip
    assert result["reply"] == "Hi Alex! Option 1 fits your week."
    assert len(result["proposals"]) == 1 and result["tools_used"] == ["find_schedules", "propose_schedule"]


def test_flow_waits_for_results_when_listed_sections_have_warnings():
    """Sections Flow listed itself weren't checked before it wrote; with a warning it sees it first."""
    client = FakeClient([
        proposal_with_text("Here you go.", {"name": "Plan", "sections": ["MATH 3043-001"], "explanation": "x"}),
        text_response("Here's your plan; MATH 3043-001 is full."),
    ])
    result = run_flow(make_data(), "Build me a schedule", [], client=client, model="m")
    assert len(client.models.requests) == 2 and result["reply"].endswith("is full.")


def test_flow_finishes_early_on_clean_listed_sections():
    client = FakeClient([proposal_with_text("Here you go.", {"name": "Plan", "sections": ["CSCI 4203-001"], "explanation": "x"})])
    result = run_flow(make_data(), "Build me a schedule", [], client=client, model="m")
    assert len(client.models.requests) == 1 and result["reply"] == "Here you go."


def test_the_explanation_thinks_little_and_survives_a_model_without_that_setting():
    client = FakeClient([text_response("Fits well.")])
    suggest.explain(make_data(), [], {"conflicts": [], "warnings": []}, SuggestRequest(), client, "m")
    assert client.models.requests[0]["config"].thinking_config.thinking_level == "LOW"

    class OldModel(FakeClient):
        def __init__(self):
            super().__init__([text_response("Fits well.")])
            real = self.models.generate_content

            def generate_content(model, contents, config):
                if config.thinking_config is not None:
                    raise errors.ClientError(400, {"error": {"message": "Thinking level LOW is not supported"}})
                return real(model=model, contents=contents, config=config)
            self.models.generate_content = generate_content

    assert suggest.explain(make_data(), [], {"conflicts": [], "warnings": []}, SuggestRequest(), OldModel(), "m") == "Fits well."


def test_flow_does_not_finish_early_on_a_conflict():
    data = make_data()
    data.context.commitments = [Commitment(uuid.uuid4(), "M", time(14), time(15), "work", True)]
    tools = AdvisorTools(data)
    tools.last_options = [[data.load_sections(["CSCI 4203"])["CSCI 4203"][0]]]  # an option that hits the shift
    client = FakeClient([
        proposal_with_text("All set!", {"name": "Plan", "option": 1, "explanation": "x"}),
        text_response("That one hits your shift; here's why."),
    ])
    import app.advisor as advisor_module

    original = advisor_module.AdvisorTools
    advisor_module.AdvisorTools = lambda d: tools
    try:
        result = run_flow(data, "Build me a schedule", [], client=client, model="m")
    finally:
        advisor_module.AdvisorTools = original
    assert len(client.models.requests) == 2 and result["reply"].startswith("That one hits your shift")
