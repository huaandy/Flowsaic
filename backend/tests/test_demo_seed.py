"""The demo students' data. No database: course codes are checked against data/course_info.csv."""

import csv
import uuid
from collections import Counter

import pytest

from app.checker import Commitment, SectionInfo, StudentContext, check_schedule
from app.config import REPO_DIR
from app.demo_seed import CURRENT_TERM, DEMO_STUDENTS, DemoCourse, classification_for
from app.normalize import normalize_days, parse_export_time, split_course_section

CATALOG_CODES = {
    row["code"] for row in csv.DictReader(open(REPO_DIR / "data" / "course_info.csv", encoding="utf-8"))
}
TERM_ORDER = ["Fall 2023", "Spring 2024", "Fall 2024", "Spring 2025", "Fall 2025", "Spring 2026", CURRENT_TERM]


def by_name(name):
    return next(s for s in DEMO_STUDENTS if s.name == name)


def test_three_fake_students_on_different_plans():
    assert len(DEMO_STUDENTS) == 3
    assert len({s.email for s in DEMO_STUDENTS}) == 3
    assert len({s.plan_name for s in DEMO_STUDENTS}) == 3
    assert all(s.email.endswith("@demo.flowsaic.test") for s in DEMO_STUDENTS)  # never a real address
    assert {s.classification for s in DEMO_STUDENTS} == {"Freshman", "Junior", "Senior"}
    assert any(s.plan_name == "Computer Science, BS" for s in DEMO_STUDENTS)


@pytest.mark.parametrize("student", DEMO_STUDENTS, ids=lambda s: s.name)
def test_classification_matches_earned_hours(student):
    assert classification_for(student.earned_hours) == student.classification


def test_earned_hours():
    assert by_name("Andy Hua").earned_hours == 64  # 61 + MATH 1023 concurrent credit
    assert by_name("Aaron Ezell").earned_hours == 3
    assert by_name("Victor Santamaria").earned_hours == 95  # the F in PSYC 3183 earns nothing


@pytest.mark.parametrize("student", DEMO_STUDENTS, ids=lambda s: s.name)
def test_every_course_is_a_real_catalog_course(student):
    assert {c.code for c in student.courses} - CATALOG_CODES == set()


@pytest.mark.parametrize("student", DEMO_STUDENTS, ids=lambda s: s.name)
def test_rows_are_consistent(student):
    for course in student.courses:
        assert course.term in TERM_ORDER
        # In progress = this fall, with no grade; anything earlier has a grade.
        assert (course.term == CURRENT_TERM) == (course.status == "in_progress")
        assert course.grade is None or course.grade in {"A", "B", "C", "D", "F", "W"}
    # A course appears twice only as a retake after a failing grade.
    for code, count in Counter(c.code for c in student.courses).items():
        if count > 1:
            rows = [c for c in student.courses if c.code == code]
            assert count == 2 and rows[0].grade in {"F", "W"} and rows[1].status == "in_progress", code


def test_victor_is_retaking_a_failed_course():
    rows = [c for c in by_name("Victor Santamaria").courses if c.code == "PSYC 3183"]
    assert [(r.term, r.grade, r.status) for r in rows] == [
        ("Spring 2026", "F", "completed"),
        (CURRENT_TERM, None, "in_progress"),
    ]


def test_demo_moments_rely_on_these_rows():
    andy = {c.code: c for c in by_name("Andy Hua").courses}
    assert andy["CSCI 3213"].status == "in_progress"  # unlocks CSCI 3143 this spring
    assert andy["CSCI 3103"].status == "completed"  # adding it again -> already_completed
    assert "CSCI 4922" not in andy  # CSCI 4932 -> missing_prereq
    aaron = {c.code: c for c in by_name("Aaron Ezell").courses}
    assert "ENGL 1123" not in aaron  # MGMT 2003 -> missing_prereq


def test_credits_come_from_the_last_digit():
    assert DemoCourse("MATH 1525", "Fall 2024", "B").credits == 5
    assert DemoCourse("CSCI 2101", "Fall 2024", "A").credits == 1
    assert DemoCourse("GSTD 1002", "Fall 2024", "A").credits == 2


# --- names, commitments and preferences (Nov 20) ------------------------------------------------

def test_renamed_students_keep_their_old_emails_for_the_in_place_rename():
    assert [(s.name, s.email, s.old_emails) for s in DEMO_STUDENTS] == [
        ("Andy Hua", "andy.hua@demo.flowsaic.test", ("alex.rivera@demo.flowsaic.test",)),
        ("Aaron Ezell", "aaron.ezell@demo.flowsaic.test", ("jordan.brooks@demo.flowsaic.test",)),
        ("Victor Santamaria", "victor.santamaria@demo.flowsaic.test", ("sam.okafor@demo.flowsaic.test",)),
    ]


def test_login_usernames_follow_the_rename():
    from app.auth import login_email

    assert [login_email(u) for u in ("1", "2", "3")] == [s.email for s in DEMO_STUDENTS]


@pytest.mark.parametrize("student", DEMO_STUDENTS, ids=lambda s: s.name)
def test_events_are_valid_rows(student):
    assert student.events
    titles_by_fixed = {}
    for event in student.events:
        assert event.day in "MTWRF" and len(event.day) == 1
        assert event.start < event.end
        assert event.category in {"work", "personal_study", "extracurricular"}
        titles_by_fixed.setdefault(event.title, set()).add(event.fixed)
        row = event.row(uuid.uuid4())
        assert row["location"] is None and row["recurrence"] == "weekly"
    # A title is either fixed or flexible, so re-seeding by title replaces exactly these rows.
    assert all(len(kinds) == 1 for kinds in titles_by_fixed.values())


def test_preferences():
    andy, aaron, victor = (s.preferences for s in DEMO_STUDENTS)
    assert andy.preferred_time == "morning"
    assert (aaron.preferred_time, aaron.min_credits, aaron.flexibility, set(aaron.delivery)) == (
        "afternoon", 12, "strict", {"in_person", "online"})
    assert (victor.preferred_days, victor.min_credits, victor.max_credits, victor.flexibility) == (
        "MTWR", 12, 15, "balanced")


def spring_sections() -> dict[str, SectionInfo]:
    """The committed Spring 2027 schedule file, as checker sections keyed 'CODE-NNN'."""
    sections = {}
    with open(REPO_DIR / "data" / "sections_spring_2027.csv", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            code, number = split_course_section(row["course_section"])
            sections.setdefault(f"{code}-{number}", SectionInfo(
                id=uuid.uuid4(), code=code, section_number=number, title=None, credits=3.0,
                days=normalize_days(row["days"]), start=parse_export_time(row["start_time"]),
                end=parse_export_time(row["end_time"]), instructor="Staff", enrolled=0, capacity=30))
    return sections


# Which real sections each student's commitments are meant to hit in the demo.
DEMO_HITS = {
    "Andy Hua": {"commitment_overlap": {"CSCI 4203-001", "MATH 3043-002"},
                 "commitment_overlap_flexible": {"CSCI 3143-001"}},
    "Aaron Ezell": {"commitment_overlap": {"ACCT 2003-001", "ECON 2103-001"},
                    "commitment_overlap_flexible": {"ENGL 1123-010", "IS 2053-002"}},
    "Victor Santamaria": {"commitment_overlap": {"PSYC 3153-001"},
                          "commitment_overlap_flexible": {"PSYC 4043-001"}},
}


@pytest.mark.parametrize("student", DEMO_STUDENTS, ids=lambda s: s.name)
def test_commitments_hit_real_spring_sections(student):
    sections = spring_sections()
    context = StudentContext({}, {}, {}, None, [
        Commitment(uuid.uuid4(), e.day, e.start, e.end, e.category, e.fixed) for e in student.events])
    for code, labels in DEMO_HITS[student.name].items():
        for label in labels:
            result = check_schedule([sections[label]], context)
            found = {item["code"] for item in result["conflicts"] + result["warnings"]}
            assert code in found, (label, found)
            # Category, day and time only: never the event's title.
            for item in result["conflicts"] + result["warnings"]:
                assert not any(e.title in item["message"] for e in student.events)


def test_aaron_keeps_the_tr_morning_sections():
    sections = spring_sections()
    context = StudentContext({}, {}, {}, None, [
        Commitment(uuid.uuid4(), e.day, e.start, e.end, e.category, e.fixed) for e in DEMO_STUDENTS[1].events])
    assert check_schedule([sections["ENGL 1123-003"]], context)["conflicts"] == []  # TR 09:30
