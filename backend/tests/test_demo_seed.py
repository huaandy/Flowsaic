"""The demo students' data. No database: course codes are checked against data/course_info.csv."""

import csv
from collections import Counter

import pytest

from app.config import REPO_DIR
from app.demo_seed import CURRENT_TERM, DEMO_STUDENTS, DemoCourse, classification_for

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
    assert by_name("Alex Rivera").earned_hours == 64  # 61 + MATH 1023 concurrent credit
    assert by_name("Jordan Brooks").earned_hours == 3
    assert by_name("Sam Okafor").earned_hours == 95  # the F in PSYC 3183 earns nothing


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


def test_sam_is_retaking_a_failed_course():
    rows = [c for c in by_name("Sam Okafor").courses if c.code == "PSYC 3183"]
    assert [(r.term, r.grade, r.status) for r in rows] == [
        ("Spring 2026", "F", "completed"),
        (CURRENT_TERM, None, "in_progress"),
    ]


def test_demo_moments_rely_on_these_rows():
    alex = {c.code: c for c in by_name("Alex Rivera").courses}
    assert alex["CSCI 3213"].status == "in_progress"  # unlocks CSCI 3143 this spring
    assert alex["CSCI 3103"].status == "completed"  # adding it again -> already_completed
    assert "CSCI 4922" not in alex  # CSCI 4932 -> missing_prereq
    jordan = {c.code: c for c in by_name("Jordan Brooks").courses}
    assert "ENGL 1123" not in jordan  # MGMT 2003 -> missing_prereq


def test_credits_come_from_the_last_digit():
    assert DemoCourse("MATH 1525", "Fall 2024", "B").credits == 5
    assert DemoCourse("CSCI 2101", "Fall 2024", "A").credits == 1
    assert DemoCourse("GSTD 1002", "Fall 2024", "A").credits == 2
