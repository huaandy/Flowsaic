"""The offline Gemini prereq pass. Gemini is faked; nothing here calls the API."""

import csv

from app.catalog.prereq_proposals import (
    check_proposal,
    needs_a_look,
    parse_answer,
    propose,
    select_rows,
    write_proposals,
)
from app.config import REPO_DIR
from tests.test_advisor import FakeClient, text_response

ROW_HS = {"code": "HS 4433", "title": "Sports Medicine", "prereq_text": "HS 2043 and HS 2443, or instructor permission.",
          "prereqs": "", "other_requirements": "or instructor permission", "needs_review": "and/or mix"}
ROW_MATH = {"code": "MATH 2124", "title": "Applied Calculus",
            "prereq_text": "ACT math subscore of 26 or higher, or MATH 1023 and MATH 1033, or MATH 1045.",
            "prereqs": "", "other_requirements": "", "needs_review": "and/or mix"}


def test_which_courses_get_a_look():
    assert needs_a_look(ROW_HS)
    assert needs_a_look({**ROW_HS, "needs_review": "", "prereqs": "PHYS 2103+PHYS 2101|PHYS 2213+PHYS 2211"})
    assert needs_a_look({**ROW_HS, "needs_review": "", "prereqs": "ENGL 2213|ENGL 2223;HUM 2003"})
    assert not needs_a_look({**ROW_HS, "needs_review": "", "prereqs": "CSCI 2113"})
    assert not needs_a_look({**ROW_HS, "prereq_text": ""})  # broken page: nothing to read


def test_selects_from_the_committed_csv():
    rows = select_rows(REPO_DIR / "data" / "course_info.csv")
    selected = {row["code"] for row in rows}
    assert {"ENGR 2033", "ETEC 4003", "ENGL 4333", "HS 4433"} <= selected
    assert "CSCI 3103" not in selected
    assert [r["code"] for r in select_rows(REPO_DIR / "data" / "course_info.csv", {"HS 4433"})] == ["HS 4433"]


def test_parse_answer_tolerates_a_fence_and_rejects_junk():
    answer = '```json\n[{"code": "HS  4433", "prereqs": "HS 2043+HS 2443", "other_requirements": "or instructor permission"}]\n```'
    [proposal] = parse_answer(answer)
    assert (proposal.code, proposal.prereqs, proposal.note) == ("HS 4433", "HS 2043+HS 2443", "")
    assert parse_answer("not json") == []
    assert parse_answer('{"code": "X 1003"}')[0].prereqs == ""


def test_code_checks_every_proposal():
    [good] = parse_answer('[{"code": "HS 4433", "prereqs": "HS 2043+HS 2443"}]')
    assert check_proposal(ROW_HS, good) == ("yes", "")
    [bad_syntax] = parse_answer('[{"code": "HS 4433", "prereqs": "HS 2043 and HS 2443"}]')
    assert check_proposal(ROW_HS, bad_syntax)[0] == "no"
    [invented] = parse_answer('[{"code": "HS 4433", "prereqs": "HS 2043+HS 9999"}]')
    assert check_proposal(ROW_HS, invented) == ("no", "names courses not in the catalog wording: HS 9999")
    assert check_proposal(ROW_HS, None) == ("no", "no answer for this course")


def test_propose_sends_only_catalog_wording_and_writes_a_review_file(tmp_path):
    client = FakeClient([text_response(
        '[{"code": "HS 4433", "prereqs": "HS 2043+HS 2443", "other_requirements": "or instructor permission"},'
        ' {"code": "MATH 2124", "prereqs": "", "other_requirements": "ACT math subscore of 26",'
        '  "note": "an ACT score can replace the courses"}]')])
    rows = propose([ROW_HS, ROW_MATH], client, "m", log_line=lambda _line: None)
    [request] = client.models.requests
    sent = request["contents"][0].parts[0].text
    assert "HS 4433 (Sports Medicine): HS 2043 and HS 2443" in sent
    assert request["config"].tools is None and request["config"].temperature == 0
    assert [(r["code"], r["valid"], r["proposed_prereqs"]) for r in rows] == [
        ("HS 4433", "yes", "HS 2043+HS 2443"), ("MATH 2124", "yes", "")]
    assert rows[1]["model_note"] == "an ACT score can replace the courses"

    path = tmp_path / "proposals.csv"
    write_proposals(rows, path)
    with open(path, newline="", encoding="utf-8") as file:
        written = list(csv.DictReader(file))
    assert written[0]["current_needs_review"] == "and/or mix" and written[0]["model"] == "m"


def test_a_failed_batch_is_written_as_not_valid():
    class Broken:
        class models:  # noqa: N801
            @staticmethod
            def generate_content(**_kwargs):
                raise RuntimeError("quota")

    rows = propose([ROW_HS], Broken(), "m", log_line=lambda _line: None)
    assert rows[0]["valid"] == "no" and "RuntimeError" in rows[0]["check_note"]


def test_proposals_are_never_read_by_the_loader():
    # Only the overrides file (reviewed rows) reaches the CSV; the proposals file is not an input.
    from app.catalog import course_pages

    assert course_pages.OVERRIDES_PATH.name == "course_prereq_overrides.csv"
    source = (REPO_DIR / "backend" / "app" / "catalog" / "course_pages.py").read_text(encoding="utf-8")
    assert "course_prereq_proposals" not in source
