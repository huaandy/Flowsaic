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
    assert "Quick replies:" not in result["memory"]  # the raw line never reaches history...
    # ...but Flow remembers which buttons it offered (Nov 20).
    assert result["memory"].endswith("\n[Quick replies offered: 12 credits | 15 credits | Not sure yet]")


def test_a_schedule_in_text_only_gets_a_show_as_schedule_button():
    client = FakeClient([text_response("Swap in CSCI 4353 Deep Learning and keep CSCI 4203 Database Design.\n"
                                       "Quick replies: Looks good | Keep Fridays free | Fewer credits")])
    result = run_flow(make_data(), "Swap my elective", [], client=client, model="m")
    assert result["proposals"] == []
    assert result["suggestions"] == [SHOW_AS_SCHEDULE, "Looks good", "Keep Fridays free"]


def test_no_show_as_schedule_button_when_flow_lists_options_and_asks():
    # Nov 20: a reply listing electives and asking which one isn't a schedule; Flow's own
    # quick replies (the answers) keep all three places.
    client = FakeClient([text_response(
        "Options:\n- CSCI 4353 Deep Learning\n- CSCI 4223 Cyber Forensics\n\n**Which of these interests you most?**\n"
        "Quick replies: Add CSCI 4353 Deep Learning | Add CSCI 4223 Cyber Forensics | Not sure yet")])
    result = run_flow(make_data(), "Which elective?", [], client=client, model="m")
    assert result["suggestions"] == ["Add CSCI 4353 Deep Learning", "Add CSCI 4223 Cyber Forensics", "Not sure yet"]


def test_asks_a_question():
    assert advisor.asks_a_question("Here are two.\nWhich one?")
    assert advisor.asks_a_question("Want me to build it?**  ")
    assert not advisor.asks_a_question("Is that ok? Here is the plan: CSCI 4203 and CSCI 4353.")
    assert not advisor.asks_a_question("")


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


# --- a tapped button keeps its meaning (Nov 20) -------------------------------------------------------

def user_text(request) -> str:
    return request["contents"][-1].parts[0].text


ASKED = {"role": "assistant",
         "text": "Which elective do you want?\n[Quick replies offered: CSCI 4353 Deep Learning | CSCI 4153 | Not sure yet]"}


def test_a_tapped_quick_reply_reaches_gemini_with_context():
    client = FakeClient([text_response("Great, adding CSCI 4353.")])
    history = [{"role": "user", "text": "Help me pick an elective"}, ASKED]
    run_flow(make_data(), "csci 4153", history, client=client, model="m")  # case doesn't matter
    sent = user_text(client.models.requests[0])
    assert sent == "csci 4153\n" + advisor.TAPPED_NOTE


def test_a_typed_message_is_sent_unchanged():
    client = FakeClient([text_response("Sure.")])
    run_flow(make_data(), "CSCI 4153 instead please", [ASKED], client=client, model="m")
    assert user_text(client.models.requests[0]) == "CSCI 4153 instead please"


def test_only_the_last_replys_buttons_count():
    older = [ASKED, {"role": "user", "text": "Not sure yet"},
             {"role": "assistant", "text": "No problem. Anything else?"}]
    assert advisor.offered_quick_replies(older) == []
    assert advisor.with_quick_reply_context("CSCI 4153", older) == "CSCI 4153"
    assert advisor.offered_quick_replies([]) == []


def test_flow_is_told_buttons_must_stand_on_their_own():
    assert "not just \"CSCI 4353\"" in FLOW_INSTRUCTIONS
    assert "one of the quick replies you offered" in FLOW_INSTRUCTIONS


def test_a_copied_offered_line_never_shows_in_the_reply():
    client = FakeClient([text_response("Done.\n[Quick replies offered: A | B]\nQuick replies: Save it | Change it")])
    result = run_flow(make_data(), "ok", [], client=client, model="m")
    assert result["reply"] == "Done." and result["suggestions"] == ["Save it", "Change it"]


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
