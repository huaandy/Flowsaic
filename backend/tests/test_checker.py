"""The schedule checker (every code), the solver, and their endpoints. Fake sections; no database."""

import uuid
from datetime import time

import pytest
from fastapi.testclient import TestClient

from app import checker, solver
from app.checker import PlanScope, SectionInfo, StudentContext, check_schedule
from app.progress import parse_electives


def section(code, number="001", days="MW", start=(10, 0), end=(10, 50), credits=3, enrolled=5, capacity=30,
            instructor="Pat Doe"):
    return SectionInfo(
        id=uuid.uuid4(), code=code, section_number=number, title=None, credits=credits, days=days,
        start=time(*start) if start else None, end=time(*end) if end else None, instructor=instructor,
        enrolled=enrolled, capacity=capacity,
    )


def student(passed=(), in_progress=(), prereqs=None, plan=None):
    return StudentContext({c: 3.0 for c in passed}, {c: 3.0 for c in in_progress}, prereqs or {}, plan)


def codes(result, kind):
    return [entry["code"] for entry in result[kind]]


# --- conflicts -------------------------------------------------------------------------------

def test_time_overlap():
    a = section("CSCI 4203", days="MW", start=(14, 10), end=(15, 30))
    b = section("MATH 3043", "002", days="MW", start=(14, 10), end=(15, 30))
    result = check_schedule([a, b], student())
    assert result["conflicts"] == [{"code": "time_overlap", "section_ids": [a.id, b.id],
                                    "message": "CSCI 4203 and MATH 3043 overlap on MW 14:10"}]


@pytest.mark.parametrize(("b_days", "b_start", "b_end", "overlaps"), [
    ("TR", (10, 0), (10, 50), False),  # different days
    ("MWF", (10, 50), (11, 40), False),  # touching ends: start_a < end_b is false
    ("F", (10, 0), (10, 50), False),
    ("WF", (10, 30), (11, 0), True),  # shares Wednesday, overlaps 10:30-10:50
    (None, None, None, False),  # online never overlaps
])
def test_overlap_rule(b_days, b_start, b_end, overlaps):
    a = section("ZOO 1003", days="MW", start=(10, 0), end=(10, 50))
    b = section("ZOO 2003", days=b_days, start=b_start, end=b_end)
    assert (codes(check_schedule([a, b], student()), "conflicts") == ["time_overlap"]) == overlaps


def test_overlap_message_lists_only_shared_days():
    a = section("ZOO 1003", days="MWF", start=(9, 0), end=(9, 50))
    b = section("ZOO 2003", days="TWR", start=(9, 30), end=(10, 20))
    assert check_schedule([a, b], student())["conflicts"][0]["message"] == "ZOO 1003 and ZOO 2003 overlap on W 09:30"


def test_missing_prereq_and_or_groups():
    prereqs = {"CSCI 4932": [["CSCI 4922"]], "MATH 2753": [["MATH 1525", "MATH 2125"]], "CSCI 3143": [["CSCI 3213"]]}
    sections = [section("CSCI 4932"), section("MATH 2753", days="TR"), section("CSCI 3143", days="F")]
    # MATH 2753: one OR option passed. CSCI 3143: its prereq is in progress, which counts.
    result = check_schedule(sections, student(passed=["MATH 2125"], in_progress=["CSCI 3213"], prereqs=prereqs))
    assert [(e["code"], e["message"]) for e in result["conflicts"]] == [
        ("missing_prereq", "CSCI 4932 needs CSCI 4922 (passed or in progress)")]


def test_a_prereq_in_the_same_schedule_does_not_count():
    sections = [section("ENGL 1123", days="TR"), section("MGMT 2003", days="MW")]
    result = check_schedule(sections, student(prereqs={"MGMT 2003": [["ENGL 1113"], ["ENGL 1123"]]}))
    assert result["conflicts"][0]["message"] == "MGMT 2003 needs ENGL 1113 and ENGL 1123 (passed or in progress)"


def test_duplicate_course():
    a, b = section("CSCI 4932", "001", days="MW"), section("CSCI 4932", "002", days="TR")
    result = check_schedule([a, b], student())
    assert result["conflicts"] == [{"code": "duplicate_course", "section_ids": [a.id, b.id],
                                    "message": "CSCI 4932 is in this schedule more than once (sections 001 and 002)"}]


# --- warnings --------------------------------------------------------------------------------

def test_already_completed_ignores_failed_grades():
    # The context only holds passing grades (F/W are filtered by split_taken); in progress isn't "completed".
    result = check_schedule([section("CSCI 3103"), section("PSYC 3183", days="TR")],
                            student(passed=["CSCI 3103"], in_progress=["PSYC 3183"]))
    assert [(e["code"], e["message"]) for e in result["warnings"]] == [("already_completed", "You already passed CSCI 3103")]
    assert result["conflicts"] == []


def test_section_full():
    full = section("MATH 3043", enrolled=23, capacity=20)
    result = check_schedule([full, section("ZOO 1003", days="TR", enrolled=0, capacity=0)], student())
    assert [(e["code"], e["message"]) for e in result["warnings"]] == [("section_full", "MATH 3043-001 is full (23/20 enrolled)")]


def test_not_on_plan_knows_listed_courses_and_electives():
    plan = PlanScope({"CSCI 4203"}, parse_electives("15 hours of upper-level Computer Science electives "
                                                    "3 hours of unrestricted electives"), has_open_electives=True)
    sections = [section("CSCI 4203"), section("CSCI 4353", days="TR"), section("CSCI 2103", days="F"),
                section("ART 1103", days="S")]
    result = check_schedule(sections, student(plan=plan))
    assert [e["message"] for e in result["warnings"]] == [
        "CSCI 2103 isn't on your degree plan (it would count as a general elective)",
        "ART 1103 isn't on your degree plan (it would count as a general elective)",
    ]
    assert codes(check_schedule(sections, student(plan=None)), "warnings") == []  # no plan yet: no warning


def test_over_credit_limit_counts_each_course_once():
    sections = [section(f"ZOO {n}003", days=d, credits=3) for n, d in zip(range(1, 7), "MTWRFS", strict=True)]
    sections.append(section("ZOO 7101", days="U", credits=1))
    result = check_schedule(sections, student())
    assert [(e["code"], e["message"]) for e in result["warnings"]] == [("over_credit_limit", "19 credits is over the 18-credit limit")]
    assert codes(check_schedule(sections[:6], student()), "warnings") == []  # exactly 18 is fine


# --- solver ----------------------------------------------------------------------------------

SECTIONS = {
    "CSCI 3143": [section("CSCI 3143", days="TR", start=(15, 40), end=(17, 0))],
    "CSCI 4203": [section("CSCI 4203", days="MW", start=(14, 10), end=(15, 30))],
    "MATH 3043": [section("MATH 3043", "001", days="MWF", start=(10, 0), end=(10, 50), enrolled=23, capacity=20),
                  section("MATH 3043", "002", days="MW", start=(14, 10), end=(15, 30))],
    "ENGL 3023": [section("ENGL 3023", "001", days="T", start=(9, 30), end=(10, 50)),
                  section("ENGL 3023", "029", days=None, start=None, end=None)],
    "MATH 2753": [section("MATH 2753", days="TR", start=(12, 40), end=(14, 0))],
}


def test_solver_avoids_overlaps_and_respects_constraints():
    c = solver.Constraints(days_off="F", earliest_start=time(10, 0))
    result = solver.search(["CSCI 4203", "MATH 3043"], [], SECTIONS, c)
    # MATH 3043-002 overlaps CSCI 4203 and -001 meets Fridays: nothing fits.
    assert result["schedules"] == [] and result["message"] == "no combination fits without a time overlap"
    result = solver.search(["CSCI 4203", "MATH 3043"], [], SECTIONS, solver.Constraints())
    [only] = result["schedules"]
    assert [s.label for s in only["sections"]] == ["CSCI 4203-001", "MATH 3043-001"]


def test_solver_fills_to_the_credit_target_best_first():
    c = solver.Constraints(min_credits=9, max_credits=9, earliest_start=time(10, 0))
    result = solver.search(["CSCI 4203"], ["MATH 2753", "ENGL 3023", "CSCI 3143"], SECTIONS, c)
    labels = [[s.label for s in sched["sections"]] for sched in result["schedules"]]
    # ENGL 3023-001 starts at 09:30, so only the online section is allowed.
    assert labels[0] == ["CSCI 4203-001", "MATH 2753-001", "ENGL 3023-029"]
    assert all(sched["credits"] == 9 for sched in result["schedules"])
    assert ["CSCI 4203-001", "MATH 2753-001", "CSCI 3143-001"] in labels


def test_solver_explains_unschedulable_courses():
    c = solver.Constraints(unavailable=[solver.Block("MTWRF", time(8), time(17))], allow_online=False)
    result = solver.search(["CSCI 4203", "ZOO 9999"], [], SECTIONS, c)
    assert result["unschedulable"] == [
        {"code": "CSCI 4203", "reason": "no section fits: meets during unavailable time"},
        {"code": "ZOO 9999", "reason": "not offered this term"},
    ]


def test_solver_hard_filters():
    c = solver.Constraints(open_seats_only=True, avoid_instructors=["Lee"])
    lee = section("ZOO 1003", instructor="Lee Roe")
    assert solver.why_not(lee, c) == "instructor to avoid"
    assert solver.why_not(SECTIONS["MATH 3043"][0], c) == "full"
    assert solver.why_not(SECTIONS["ENGL 3023"][1], solver.Constraints(allow_online=False)) == "online or TBA"
    assert solver.why_not(SECTIONS["CSCI 4203"][0], solver.Constraints(latest_end=time(15))) == "ends too late"


def test_solver_ranks_preferences():
    early = section("ZOO 1003", "001", days="MW", start=(8, 0), end=(8, 50))
    late = section("ZOO 1003", "002", days="MW", start=(13, 0), end=(13, 50), instructor="Ann Smith")
    result = solver.search(["ZOO 1003"], [], {"ZOO 1003": [early, late]},
                           solver.Constraints(preferred_time="afternoon", preferred_instructors=["Smith"]))
    assert [s["sections"][0].section_number for s in result["schedules"]] == ["002", "001"]


# --- endpoints -------------------------------------------------------------------------------

@pytest.fixture
def signed_in(monkeypatch):
    from app import auth
    from app.main import app
    from app.routers import auth as auth_router

    student_id = uuid.uuid4()
    monkeypatch.setattr(auth, "find_student_id", lambda email: student_id)
    monkeypatch.setattr(auth_router, "load_profile", lambda sid: {
        "id": sid, "name": "Zed", "email": "z@demo.flowsaic.test", "classification": None, "major": None,
        "catalog_year": None, "degree_plan": None, "has_hold": False, "total_hours_earned": None,
        "total_hours_needed": None, "audit_refreshed_at": None, "connected_mysau": False})
    client = TestClient(app)
    return client, student_id


def test_check_endpoint(signed_in, monkeypatch):
    client, student_id = signed_in
    a, b = SECTIONS["CSCI 4203"][0], SECTIONS["MATH 3043"][1]
    calls = []

    def fake(sid, section_ids, term_id):
        calls.append((sid, section_ids, term_id))
        return check_schedule([a, b], student())

    monkeypatch.setattr(checker, "check_for_student", fake)
    term_id = uuid.uuid4()
    assert client.post("/schedules/check", json={"term_id": str(term_id), "section_ids": []}).status_code == 401
    client.post("/auth/login", json={"email": "1"})
    body = client.post("/schedules/check", json={"term_id": str(term_id), "section_ids": [str(a.id), str(b.id), str(a.id)]}).json()
    assert [c["code"] for c in body["conflicts"]] == ["time_overlap"] and body["warnings"] == []
    assert calls == [(student_id, [a.id, b.id], term_id)]  # duplicates in the request are dropped
    assert client.post("/schedules/check", json={"term_id": str(term_id), "section_ids": []}).json() == {"conflicts": [], "warnings": []}
    assert client.post("/schedules/check", json={"section_ids": []}).json() == {"error": "invalid_request"}


@pytest.mark.parametrize(("error", "status", "code"), [
    (checker.SectionNotFound([1]), 404, "section_not_found"),
    (checker.SectionNotInTerm(), 422, "section_not_in_term"),
])
def test_check_endpoint_errors(signed_in, monkeypatch, error, status, code):
    client, _ = signed_in

    def fail(*args):
        raise error

    monkeypatch.setattr(checker, "check_for_student", fail)
    client.post("/auth/login", json={"email": "1"})
    response = client.post("/schedules/check", json={"term_id": str(uuid.uuid4()), "section_ids": [str(uuid.uuid4())]})
    assert response.status_code == status and response.json() == {"error": code}
