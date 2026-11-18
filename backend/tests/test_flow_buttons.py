"""Flow's buttons (Nov 18): quick replies taken out of the reply text, a "Show this as a schedule"
button when Flow described a schedule without a card, and the instruction to always make a card.
Gemini is mocked; no database."""

import pytest

from app import advisor, suggest
from app.advisor import FLOW_INSTRUCTIONS, SHOW_AS_SCHEDULE, run_flow, split_quick_replies
from app.suggest import SuggestRequest
from tests.test_advisor import FakeClient, call_response, make_data, text_response


@pytest.mark.parametrize(("text", "expected_text", "expected"), [
    ("How many credits?\nQuick replies: 12 credits | 15 credits | Not sure yet",
     "How many credits?", ["12 credits", "15 credits", "Not sure yet"]),
    ("Done.\n\n**Quick replies:** \"Keep Fridays free\" | Make it lighter |  | keep fridays free",
     "Done.", ["Keep Fridays free", "Make it lighter"]),
    ("Sure.\nquick-replies: A | B | C | D", "Sure.", ["A", "B", "C"]),  # at most 3
    ("No line here.", "No line here.", []),
    ("Ok.\nQuick replies: Add a 5th course (15 cr) | [Looks great!] | (Keep mornings free)",
     "Ok.", ["Add a 5th course (15 cr)", "Looks great!", "Keep mornings free"]),  # inner brackets stay
    ("Quick replies: " + "x" * 70 + " | Fine", "", ["Fine"]),  # too long for a button
])
def test_split_quick_replies(text, expected_text, expected):
    assert split_quick_replies(text) == (expected_text, expected)


def test_flow_returns_quick_replies_and_keeps_them_out_of_the_text():
    client = FakeClient([text_response("Hi {first_name}! How many credits do you want?\n"
                                       "Quick replies: 12 credits | 15 credits | Not sure yet")])
    result = run_flow(make_data(), "Plan my spring", [], client=client, model="m")
    assert result["reply"] == "Hi Alex! How many credits do you want?"
    assert result["suggestions"] == ["12 credits", "15 credits", "Not sure yet"]
    assert "Quick replies" not in result["memory"]  # history stays clean


def test_a_schedule_in_text_only_gets_a_show_as_schedule_button():
    client = FakeClient([text_response("Swap in CSCI 4353 Deep Learning and keep CSCI 4203 Database Design.\n"
                                       "Quick replies: Looks good | Keep Fridays free | Fewer credits")])
    result = run_flow(make_data(), "Swap my elective", [], client=client, model="m")
    assert result["proposals"] == []
    assert result["suggestions"] == [SHOW_AS_SCHEDULE, "Looks good", "Keep Fridays free"]


def test_no_show_as_schedule_button_when_there_is_a_card():
    client = FakeClient([
        call_response(("propose_schedule", {"name": "Plan", "sections": ["CSCI 4203-001", "CSCI 4353-001"], "explanation": "x"})),
        text_response("CSCI 4203 and CSCI 4353 fit well.\nQuick replies: Save it | Keep Fridays free"),
    ])
    result = run_flow(make_data(), "Build it", [], client=client, model="m")
    assert len(result["proposals"]) == 1 and SHOW_AS_SCHEDULE not in result["suggestions"]


def test_one_course_mentioned_is_not_a_schedule():
    client = FakeClient([text_response("CSCI 4203 covers SQL and database design.")])
    assert run_flow(make_data(), "What's CSCI 4203?", [], client=client, model="m")["suggestions"] == []


def test_flow_is_told_to_make_a_card_every_time_and_to_add_quick_replies():
    assert "EVERY time you present, recommend or change a schedule" in FLOW_INSTRUCTIONS
    assert "Never describe a schedule in text only" in FLOW_INSTRUCTIONS
    assert "Quick replies:" in FLOW_INSTRUCTIONS


def test_the_advisor_endpoint_returns_suggestions(monkeypatch):
    from tests.test_advisor import fake_result
    from tests.test_planning import signed_in

    monkeypatch.setattr(advisor, "advise", lambda sid, message, history: {**fake_result(), "suggestions": ["12 credits"]})
    client = signed_in(monkeypatch, __import__("uuid").uuid4())
    body = client.post("/ai/advisor", json={"message": "hi"}).json()
    assert body["suggestions"] == ["12 credits"] and len(body["proposals"]) == 1


def test_auto_generate_explanations_never_show_a_quick_replies_line():
    client = FakeClient([text_response("This fits your week.\nQuick replies: Save it | Change it")])
    result = suggest.suggest(make_data(), SuggestRequest(), client, "m")
    assert result.explanation == "This fits your week."
