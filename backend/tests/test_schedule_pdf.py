"""GET /schedules/{id}/pdf: the advisor-review PDF (Nov 20). No database; Chromium only for
the one render test, which is skipped cleanly when Chromium isn't installed."""

import uuid
from datetime import UTC, datetime, time
from types import SimpleNamespace

import pytest

from app import schedule_pdf
from app.auth import ApiError
from app.schedule_pdf import Report, commitment_rows, left_after_term, prereq_status, render_html
from tests.test_checker import signed_in  # noqa: F401 - fixture

EVENTS = [
    SimpleNamespace(title="Secret Shift at Taco Place", location="123 Private Rd", category="work", day="T",
                    start_time=time(13, 0), end_time=time(17, 0), fixed=True),
    SimpleNamespace(title="Therapy", location="Clinic", category="personal_study", day="M",
                    start_time=time(9, 30), end_time=time(11, 0), fixed=False),
]


def sample_report(**overrides) -> Report:
    prereqs = {"CSCI 3143": [["CSCI 3213"]], "ENGR 2033": [["PHYS 2103 + PHYS 2101", "PHYS 2213 + PHYS 2211"]],
               "CSCI 4203": [["CSCI 3103"]]}
    passed = {"CSCI 3103": 3.0, "PHYS 2103": 3.0}
    in_progress = {"CSCI 3213": 3.0, "PHYS 2101": 1.0}
    values = dict(
        student={"name": "Andy Hua", "major": "Computer Science, BS", "catalog_year": "2026-2027",
                 "classification": "Junior", "hours_earned": 64.0, "hours_needed": 120.0, "has_hold": False,
                 "plan_source": "degree_plan"},
        schedule={"name": "Plan A <draft>", "term": "Spring 2027", "source": "ai",
                  "created_at": datetime(2026, 11, 20, tzinfo=UTC), "credits": 9.0},
        sections=[
            {"code": "CSCI 3143", "title": "Network Security", "section_number": "001", "days": "TR",
             "start_time": "15:40", "end_time": "17:00", "instructor": "Staff", "location": "Wilson Hall 106",
             "credits": 3.0, "active": True, "requirements": ["Computer Science core"]},
            {"code": "CSCI 4203", "title": "Database Design", "section_number": "001", "days": "MW",
             "start_time": "14:10", "end_time": "15:30", "instructor": "Pat Doe", "location": None,
             "credits": 3.0, "active": True, "requirements": []},
            {"code": "ENGR 2033", "title": "Statics", "section_number": "001", "days": None, "start_time": None,
             "end_time": None, "instructor": "Staff", "location": None, "credits": 3.0, "active": False,
             "requirements": ["6 hours of upper-level electives"]},
        ],
        prereqs=[prereq_status(c, prereqs, passed, in_progress) for c in ("CSCI 3143", "CSCI 4203", "ENGR 2033")],
        conflicts=[],
        warnings=["CSCI 3143-001 overlaps your flexible personal/study commitment (T 16:00-17:00)"],
        left=[{"name": "Senior project", "hours": "0 of 3 hours", "this_schedule": []}],
        commitments=commitment_rows(EVENTS),
        freshness={"audit_refreshed_at": None, "schedule_term": "Spring 2027",
                   "schedule_export_at": datetime(2026, 11, 17, tzinfo=UTC)},
        generated_at=datetime(2026, 11, 20, 18, 4, tzinfo=UTC),
    )
    values.update(overrides)
    return Report(**values)


# --- pure parts --------------------------------------------------------------------------------

def test_prereq_status_flags_in_progress_and_sets():
    passed, ip = {"CSCI 3103": 3.0, "PHYS 2103": 3.0}, {"CSCI 3213": 3.0, "PHYS 2101": 1.0}
    prereqs = {"CSCI 3143": [["CSCI 3213"]], "CSCI 4203": [["CSCI 3103"]],
               "ENGR 2033": [["PHYS 2103 + PHYS 2101", "PHYS 2213 + PHYS 2211"]], "MATH 4003": [["MATH 3003"]]}
    assert prereq_status("CSCI 4203", prereqs, passed, ip)["groups"][0]["state"] == "passed"
    item = prereq_status("CSCI 3143", prereqs, passed, ip)
    assert item["only_in_progress"] and item["groups"][0]["pending"] == ["CSCI 3213"]
    pair = prereq_status("ENGR 2033", prereqs, passed, ip)["groups"][0]
    assert pair["state"] == "in_progress" and pair["met_by"] == "PHYS 2103 + PHYS 2101" and pair["pending"] == ["PHYS 2101"]
    assert prereq_status("MATH 4003", prereqs, passed, ip)["groups"][0]["state"] == "missing"
    assert prereq_status("ART 1003", prereqs, passed, ip) == {"code": "ART 1003", "groups": [], "only_in_progress": False}


def test_left_after_term_lists_the_most_specific_open_requirements():
    tree = [{"name": "Major", "status": "not_met", "hours_required": None, "hours_done": 0, "hours_in_progress": 0,
             "courses": [], "electives": [], "children": [
                 {"name": "Core", "status": "in_progress", "courses": [{"code": "CSCI 3143"}], "children": []},
                 {"name": "Electives", "status": "not_met", "hours_required": 9, "hours_done": 3,
                  "hours_in_progress": 3, "courses": [{"code": "CSCI 4203"}, {"code": "CSCI 4353"}],
                  "electives": [], "children": []}]},
            {"name": "Gen ed", "status": "met", "courses": [], "children": []}]
    assert left_after_term(tree, {"CSCI 4203", "CSCI 3143"}) == [
        {"name": "Electives", "hours": "6 of 9 hours", "this_schedule": ["CSCI 4203"], "covered": False}]


def test_audit_blocks_covered_by_the_schedule_and_generic_names():
    # A connected student's audit statuses are used as is, so a block this schedule fills stays
    # not_met; its hours show it is covered. Generic audit names get their parent's.
    tree = [{"name": "UL CS/Math Electives", "status": "in_progress", "children": [
        {"name": "Select 3-5 hours:", "status": "not_met", "hours_required": 3.0, "hours_done": 0.0,
         "hours_in_progress": 3.0, "courses": [{"code": "MATH 4533"}, {"code": "MATH 3143"}], "children": []}]},
        {"name": "Freshman Seminar", "status": "not_met", "hours_required": None, "courses": [], "children": []}]
    assert left_after_term(tree, {"MATH 4533"}) == [
        {"name": "UL CS/Math Electives: select 3-5 hours", "hours": "3 of 3 hours", "this_schedule": ["MATH 4533"],
         "covered": True},
        {"name": "Freshman Seminar", "hours": "", "this_schedule": [], "covered": False}]
    page = render_html(sample_report(left=left_after_term(tree, {"MATH 4533"})))
    still, covered = page.split("Covered by this schedule once its courses are passed")
    assert "Freshman Seminar" in still and "UL CS/Math Electives: select 3-5 hours" in covered


def test_requirement_label():
    assert schedule_pdf.requirement_label("Select 3-5 hours:", "Math") == "Math: select 3-5 hours"
    assert schedule_pdf.requirement_label("Computer Science", "Major") == "Computer Science"
    assert schedule_pdf.requirement_label("Select 3 hours", None) == "Select 3 hours"


def test_commitments_keep_category_day_and_time_only():
    rows = commitment_rows(EVENTS)
    assert rows == [{"category": "Personal / study", "day": "M", "time": "09:30-11:00", "fixed": False},
                    {"category": "Work", "day": "T", "time": "13:00-17:00", "fixed": True}]


def test_html_has_what_an_advisor_needs():
    page = render_html(sample_report())
    for text in ("Andy Hua", "Computer Science, BS", "2026-2027", "Junior", "64 of 120", "Registration hold",
                 "CSCI 3143", "Network Security", "Tue Thu", "15:40-17:00", "Wilson Hall 106", "Computer Science core",
                 "Not on the degree plan", "Online / TBA", "no longer in the latest export", "Total credits",
                 "met only by a course in progress", "CSCI 3213, must be passed", "(PHYS 2103 and PHYS 2101)",
                 "met by CSCI 3103 (passed)", "overlaps your flexible personal/study commitment",
                 "Senior project (0 of 3 hours)", "Fixed (classes may not overlap)", "Built with Flow",
                 "exported Nov 17, 2026", "public degree map", "Generated by Flowsaic on Nov 20, 2026 at 18:04 UTC"):
        assert text in page, text


def test_html_never_has_titles_locations_email_or_signatures():
    page = render_html(sample_report())
    for event in EVENTS:
        assert event.title not in page and event.location not in page
    assert "@" not in page  # no email anywhere
    assert "signature" not in page.lower() and "approve" not in page.lower()
    assert "<draft>" not in page and "Plan A &lt;draft&gt;" in page  # escaped


def test_manual_and_audit_wording():
    page = render_html(sample_report(
        schedule={**sample_report().schedule, "source": "manual"},
        freshness={"audit_refreshed_at": datetime(2026, 11, 18, tzinfo=UTC), "schedule_term": "Spring 2027",
                   "schedule_export_at": None},
        warnings=[]))
    assert "Built by the student" in page and "mySAU degree audit, refreshed Nov 18, 2026" in page
    assert "loaded from a saved file" in page and "No warnings" in page


def test_filename_is_safe():
    assert schedule_pdf.pdf_filename('Plan "A"/ñ', "Spring 2027") == "flowsaic-spring-2027-plan-a.pdf"


# --- endpoint -----------------------------------------------------------------------------------

def test_pdf_needs_a_session():
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get(f"/schedules/{uuid.uuid4()}/pdf").json() == {"error": "not_authenticated"}


def test_pdf_of_someone_elses_schedule_is_404(signed_in, monkeypatch):  # noqa: F811
    from app.routers import schedules

    client, student_id = signed_in
    client.post("/auth/login", json={"email": "1"})
    seen = []

    def missing(sid, schedule_id):
        seen.append(sid)
        raise ApiError(404, "schedule_not_found")

    monkeypatch.setattr(schedules, "get_schedule", missing)
    response = client.get(f"/schedules/{uuid.uuid4()}/pdf")
    assert response.status_code == 404 and response.json() == {"error": "schedule_not_found"}
    assert seen == [student_id]  # always scoped to the signed-in student


def test_pdf_download(signed_in, monkeypatch):  # noqa: F811
    client, student_id = signed_in
    client.post("/auth/login", json={"email": "1"})
    asked = []
    monkeypatch.setattr(schedule_pdf, "load_report", lambda sid, schedule_id: asked.append((sid, schedule_id)) or sample_report())
    monkeypatch.setattr(schedule_pdf, "html_to_pdf", lambda page: b"%PDF-1.7 fake")
    schedule_id = uuid.uuid4()
    response = client.get(f"/schedules/{schedule_id}/pdf")
    assert response.status_code == 200 and response.content == b"%PDF-1.7 fake"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="flowsaic-spring-2027-plan-a-draft.pdf"'
    assert asked == [(student_id, schedule_id)]


def test_pdf_without_chromium_is_503(signed_in, monkeypatch):  # noqa: F811
    client, _ = signed_in
    client.post("/auth/login", json={"email": "1"})
    monkeypatch.setattr(schedule_pdf, "load_report", lambda sid, schedule_id: sample_report())

    def broken(page):
        raise schedule_pdf.PdfUnavailable("Error")

    monkeypatch.setattr(schedule_pdf, "html_to_pdf", broken)
    response = client.get(f"/schedules/{uuid.uuid4()}/pdf")
    assert response.status_code == 503 and response.json() == {"error": "pdf_unavailable"}


def test_real_render_starts_with_pdf_magic():
    try:
        data = schedule_pdf.html_to_pdf(render_html(sample_report()))
    except schedule_pdf.PdfUnavailable:
        pytest.skip("Chromium is not installed (uv run playwright install chromium)")
    assert data.startswith(b"%PDF")
    assert len(data) > 2000
