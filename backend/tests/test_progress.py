"""Degree progress and "can take this term". Pure functions with a small fake plan; no database."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.progress import (
    Offering,
    PlanGroup,
    Taken,
    build_progress,
    can_take,
    parse_electives,
    plan_progress,
    split_taken,
)

TITLES = {}

# A made-up plan:
#   Core (all): ZOO 2103, ZOO 3103
#   Humanities (all)
#     Literature choice (choose 3): LIT 2213, LIT 2223
#     Arts choice (choose 6): LIT 2223, ART 1103, MUS 2013
#   Zoo electives (all, no courses): "6 hours of upper-level Zoology electives"
#   Minor (all, no courses): "Completion of an approved minor"
GROUPS = [
    PlanGroup("core", None, "Core (6 hours)", "all", None, None, ["ZOO 2103", "ZOO 3103"]),
    PlanGroup("hum", None, "Humanities (9 hours)", "all", None, None, []),
    PlanGroup("lit", "hum", "Literature choice", "choose_hours", 3, None, ["LIT 2213", "LIT 2223"]),
    PlanGroup("arts", "hum", "Arts choice", "choose_hours", 6, None, ["LIT 2223", "ART 1103", "MUS 2013"]),
    PlanGroup("elec", None, "Electives (6 hours)", "all", None, "6 hours of upper-level Zoology electives", []),
    PlanGroup("minor", None, "Minor (15 hours)", "all", None, "Completion of an approved minor", []),
]


@pytest.fixture(autouse=True)
def zoology_subject(monkeypatch):
    from app import progress
    monkeypatch.setitem(progress.SUBJECT_PREFIXES, "zoology", ("ZOO",))


def by_name(tree, found=None):
    found = {} if found is None else found
    for node in tree:
        found[node["name"]] = node
        by_name(node["children"], found)
    return found


def test_failed_and_withdrawn_courses_are_not_passed():
    passed, in_progress = split_taken([
        Taken("ZOO 2103", "completed", "B", 3),
        Taken("ZOO 3103", "completed", "F", 3),
        Taken("ZOO 3103", "in_progress"),  # the retake
        Taken("LIT 2213", "completed", "W", 3),
        Taken("ART 1103", "completed", None, None),  # no grade (manual): counts; credits from the code
    ])
    assert passed == {"ZOO 2103": 3.0, "ART 1103": 3.0}
    assert in_progress == {"ZOO 3103": 3.0}


def test_parse_electives():
    [cs] = parse_electives("15-17 hours of upper-level Computer Science, Data Science, or Mathematics electives")
    assert (cs.hours_required, cs.level, cs.prefixes, cs.unrestricted) == (15, "upper", ("CSCI", "DSCI", "MATH"), False)
    business, free = parse_electives("6 hours of upper-level Business electives 2-8 hours of unrestricted electives")
    assert business.matches("MGMT 4073") and not business.matches("MGMT 2003") and not business.matches("CSCI 4203")
    assert (free.hours_required, free.unrestricted) == (2, True)
    [upper] = parse_electives("Up to 6 hours of non-Marketing courses may count. Upper-level Management or Marketing electives")
    assert (upper.level, upper.prefixes, upper.hours_required) == ("upper", ("MGMT", "MKTG"), None)
    assert parse_electives("10 hours of approved electives") == []  # advisor's call
    assert parse_electives("5 hours of work experience or upper-level technical electives") == []  # unknown subject
    assert parse_electives(None) == []


def test_plan_progress_statuses_and_no_double_counting():
    passed = {"ZOO 2103": 3.0, "LIT 2223": 3.0, "ART 1103": 3.0, "ZOO 4103": 3.0}
    in_progress = {"ZOO 3103": 3.0, "MUS 2013": 3.0}
    tree, needs = plan_progress(GROUPS, passed, in_progress, TITLES)
    nodes = by_name(tree)

    assert nodes["Core (6 hours)"]["status"] == "in_progress"  # ZOO 3103 is in progress
    # LIT 2223 fills the literature choice, so the arts choice can't use it again.
    assert nodes["Literature choice"]["status"] == "met"
    arts = nodes["Arts choice"]
    assert (arts["status"], arts["hours_done"], arts["hours_in_progress"]) == ("in_progress", 3.0, 3.0)
    assert {c["code"]: c["status"] for c in arts["courses"]}["LIT 2223"] == "counted_elsewhere"
    assert nodes["Humanities (9 hours)"]["status"] == "in_progress"
    # ZOO 4103 isn't listed anywhere, so it fills the upper-level Zoology elective.
    [elective] = nodes["Electives (6 hours)"]["electives"]
    assert (elective["status"], elective["hours_done"], [c["code"] for c in elective["courses"]]) == ("not_met", 3.0, ["ZOO 4103"])
    assert nodes["Electives (6 hours)"]["status"] == "not_met"
    # Nothing to track for "an approved minor": never shown as met.
    assert nodes["Minor (15 hours)"]["status"] == "not_tracked"
    assert [n for n in needs if "code" in n] == []  # every listed course is passed or in progress
    assert [n["group"] for n in needs if "elective" in n] == ["6 hours of upper-level Zoology electives"]


def test_needs_list_missing_courses():
    tree, needs = plan_progress(GROUPS, {"ZOO 2103": 3.0}, {}, TITLES)
    codes = {(n["code"], n["kind"]) for n in needs if "code" in n}
    assert ("ZOO 3103", "required") in codes
    assert ("LIT 2213", "choice") in codes and ("MUS 2013", "choice") in codes
    assert by_name(tree)["Core (6 hours)"]["status"] == "not_met"


def test_can_take_checks_offered_prereqs_and_level():
    needs = [
        {"code": "ZOO 3103", "group": "Core", "kind": "required"},
        {"code": "ZOO 4203", "group": "Core", "kind": "required"},
        {"code": "LIT 2213", "group": "Literature choice", "kind": "choice"},
        {"code": "ART 9999", "group": "Arts", "kind": "choice"},  # not offered
    ]
    elective = parse_electives("6 hours of upper-level Zoology electives")[0]
    needs.append({"elective": elective, "group": elective.text})
    offered = {code: Offering(1, 5) for code in ("ZOO 3103", "ZOO 4203", "LIT 2213", "ZOO 4403", "ZOO 5103", "ZOO 2203")}
    prereqs = {
        "ZOO 3103": [["ZOO 2103"]],  # in progress counts
        "ZOO 4203": [["ZOO 3999", "ZOO 3998"]],  # neither option done -> blocked
        "ZOO 4403": [["ZOO 2103", "ZOO 2104"]],  # an OR group with one option passed
    }
    eligible, blocked = can_take(needs, offered, prereqs, {}, {"ZOO 2103": 3.0}, TITLES, {"ZOO 3103": 4.0})
    by_code = {e["code"]: e for e in eligible}
    assert set(by_code) == {"ZOO 3103", "LIT 2213", "ZOO 4403"}
    assert by_code["ZOO 3103"]["credits"] == 4.0 and by_code["ZOO 3103"]["kind"] == "required"
    assert by_code["ZOO 4403"]["kind"] == "elective"  # ZOO 5103 is graduate level, ZOO 2203 lower level
    assert [(b["code"], b["missing_prereqs"]) for b in blocked] == [("ZOO 4203", [["ZOO 3999", "ZOO 3998"]])]
    # A course the plan lists by name is never also offered as an elective.
    assert "6 hours of upper-level Zoology electives" not in by_code["ZOO 3103"]["counts_toward"]


def test_audit_source_uses_the_audit_statuses():
    result = build_progress(
        source="audit", plan=None, term={"id": uuid.uuid4(), "name": "Spring 2027"}, groups=[],
        audit_requirements=[
            {"name": "Major", "parent_name": None, "status": "not_met", "rule": "all",
             "hours_earned": 6, "hours_required": 12, "course_options": ["ZOO 3103", "ZOO 3XXX"], "note": None},
            {"name": "Core", "parent_name": "Major", "status": "met", "rule": "all",
             "hours_earned": 6, "hours_required": 6, "course_options": [], "note": None},
        ],
        taken=[Taken("ZOO 2103", "completed", "A", 3)], titles={}, credits={},
        offered={"ZOO 3103": Offering(2, 10)}, prereqs={}, total_hours=120,
    )
    [major] = result["requirements"]
    assert (major["status"], major["hours_done"], [c["name"] for c in major["children"]]) == ("not_met", 6.0, ["Core"])
    assert [c["code"] for c in major["courses"]] == ["ZOO 3103"]  # "ZOO 3XXX" isn't a course code
    assert [c["code"] for c in result["can_take"]] == ["ZOO 3103"]
    assert result["hours"] == {"earned": 3.0, "in_progress": 0.0, "required": 120}


def test_progress_endpoint(monkeypatch):
    from app import auth
    from app.main import app
    from app.routers import me as me_router

    student_id = uuid.uuid4()
    result = build_progress(
        source="degree_plan", plan={"name": "Zoology, BS", "catalog_year": "2026-2027"},
        term={"id": uuid.uuid4(), "name": "Spring 2027"}, groups=GROUPS, audit_requirements=[],
        taken=[Taken("ZOO 2103", "completed", "A", 3)], titles={}, credits={},
        offered={"ZOO 3103": Offering(1, 0)}, prereqs={}, total_hours=120,
    )
    monkeypatch.setattr(auth, "find_student_id", lambda email: student_id)
    from app.routers import auth as auth_router

    profile = {"id": student_id, "name": "Zed", "email": "z@demo.flowsaic.test", "classification": None,
               "major": None, "catalog_year": None, "degree_plan": None, "has_hold": False,
               "total_hours_earned": None, "total_hours_needed": None, "audit_refreshed_at": None,
               "connected_mysau": False}
    monkeypatch.setattr(auth_router, "load_profile", lambda sid: profile)
    monkeypatch.setattr(me_router, "load_student_progress", lambda sid: result)
    client = TestClient(app)
    assert client.get("/me/progress").json() == {"error": "not_authenticated"}
    client.post("/auth/login", json={"email": "1"})
    body = client.get("/me/progress").json()
    assert body["source"] == "degree_plan" and body["plan"]["name"] == "Zoology, BS"
    assert [c["code"] for c in body["can_take"]] == ["ZOO 3103"]
    assert body["requirements"][0]["name"] == "Core (6 hours)"
