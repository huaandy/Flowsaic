"""Degree audit parsing. The audit below is FAKE: made-up student, made-up history.
Never put a real audit in tests or fixtures (prompt 2 privacy rules)."""

from decimal import Decimal

from app.mysau.audit_parser import AuditLine, parse_lines

# One line per audit line: "indent | flags | text". Flags: B = on a shaded header bar,
# M / X / P = met / not met / in progress icon beside the line.
FAKE_AUDIT = """
0  |   | Unofficial Advising Worksheet
0  |   | Personal Information (Legal, Home, or Permanent):
0  |   | Name: Fakerson, Testy Q.
0  |   | ID Number: 999000111
0  |   | Address: 1 Imaginary Lane
0  |   | Nowhere, AR 70000
0  |   | Phone: (555) 010-0000
0  |   | Degree Information: (Catalog Year 2024)
0  |   | Major 1: BS Imaginary Zoology
0  |   | Holds and Warnings:
0  |   | Unpaid Library Fine Hold
0  |   | Cumulative GPA:
0  |   | 3.95
0  |   | Classification:
0  |   | Junior
0  |   | Degree Hours: 64.00 / 120.00 64.00
0  |   | Advisor #1: Mentor, Imaginary
0  | BM| General Education (MET)
10 |   | General Education:.................................................12.00 Hours Earned
10 |   | General Education Requirements (12 hours)
10 |   | 3 hours of Mathematics are included in the major.
10 | BM| English Composition
20 |   | English Composition (6 hours)
20 | M | ENGL1013 Composition I (ENGL1113) A 3.00 2022 3T (TR) Imaginary Community College
20 | M | ENGL-1123-008 Composition II C 3.00 2023 1S
10 | BM| Fine Arts/Humanities
20 |   | Fine Arts/Humanities (6 hours)
20 |   | Select 3 hours of Literature and 3 hours of Fine Arts Choice.
20 | BM| Literature
30 |   | Literature Choice (3 hours)
30 |   | Select 3 hours from the following:
30 |   | - ENGL 2213 World Literature I
30 |   | - ENGL 2223 World Literature II
30 | M | ENGL-2223-002 World Literature II A 3.00 2023 2S
20 | BM| Fine Arts Choice
30 |   | Select 3 hours from the following:
30 |   | - ART 2013 Art Appreciation
30 |   | - 3 hours of Foreign Language
30 | M | ART -2013-032 Art Appreciation B 3.00 2023 1S
0  |   | Code Key:
0  |   | - Requirement is MET - Requirement is NOT MET
0  |   | Advising Worksheet (2026-11-17 02:29 am) Page 1 of 3
0  |   | Fakerson, Testy Q.
0  |   | Unofficial Advising Worksheet
0  | BM| General Education (MET)
10 |   | General Education:.................................................12.00 Hours Earned
10 |   | General Education Requirements (12 hours)
10 |   | 3 hours of Mathematics are included in the major.
0  | BX| Primary AIM: Imaginary Zoology (NOT MET) GPA:3.9000
10 |   | Imaginary Zoology:.................................................30.00 Hours Earned
10 |   | Imaginary Zoology Major Requirements
10 | BX| Zoology
20 |   | Zoology Requirements (24 hours)
20 | BM| Zoology I/Lab
30 |   | ZOO 2103/2101 Zoology I/Lab
30 | M | ZOO-2101-005 -L Zoology I Laboratory A 1.00 2023 1S
30 | M | ZOO-2103-003 Zoology I A 3.00 2023 1S
20 | M | ZOO-3103-001 Dragons D 3.00 2025 2S
20 | P | ZOO-4143-001 Unicorn Studies (3.00 In Progress AY 2026-2027 - Fall)
20 | X | ZOO4932 Senior Project II
20 | BX| UL Zoology Electives
30 |   | 6 hours of upper-level Zoology electives
30 | M | ZOO-3133-001 Griffins B 3.00 2025 1S
30 | P | Section ZOO-3903-001 is currently in progress (3.00 in AY 2026-2027 - Fall)
30 |   | Cumulative Course: 3.00 hours needed
30 | X | ZOO-3903-001 ST: Phoenixes Earned: 0.00 hours / 0 count 2026 1S
10 | BX| Mathematics
20 | M | MATH-2033-001 Discrete Mathematics B 3.00 2025 2S
20 | BM| Select 5 hours:
30 |   | Select 5 hours from the following:
30 |   | - MATH 1525 Calculus I
30 | M | MATH-1525-001 Calculus I A 5.00 2023 1S
0  |   | Advising Worksheet (2026-11-17 02:29 am) Page 2 of 3
0  |   | Fakerson, Testy Q.
10 |   | Imaginary Zoology:.................................................30.00 Hours Earned
10 |   | Imaginary Zoology Major Requirements
20 | BX| Select 3-5 hours:
30 |   | Select 3-5 hours from the following:
30 |   | - MATH 1545 Calculus II
30 |   | - MATH 4233 Data Science
10 | BM| Physics
20 |   | Select 4 hours from the following:
20 |   | - PHYS 2003/2001 College Physics I/Lab
20 | M | PHYS-2001-004 -L College Physics I Laboratory B 1.00 2024 1S
20 | M | PHYS-2003-001 College Physics I A 3.00 2024 1S
0  | BX| University Requirements (NOT MET)
10 |   | University Requirements:...........................................2.00 Hours Earned
10 |   | - Upper-Level Hours Requirement (40 hours)
10 | BX| Freshman Seminar
20 | M | GSTD-1002-019 Freshman Seminar C 2.00 2023 1S
20 | X | RESUNIVB University Residency
0  | B | Nonapplied Coursework
10 | X | HIST-2023-005 United States History II B 3.00 2024 2S
10 | M | MATH1053 College Algebra MATH1023 B 3.00 2021 2T (TR) Imaginary Community College
0  | BX| Course Totals (NOT MET)
0  |   | Total Hours Earned/Needed: 68.00 / 120.00 Overall GPA Earned/Needed: 3.95 / 2.00
0  |   | D Grade Credit Hours: 3.00
0  |   | Fakerson, Testy Q.
"""

ICONS = {"M": "met", "X": "not_met", "P": "in_progress"}


def fake_lines() -> list[AuditLine]:
    lines = []
    for raw in FAKE_AUDIT.strip("\n").splitlines():
        indent, flags, text = (part.strip() for part in raw.split("|", 2))
        icon = next((ICONS[f] for f in flags if f in ICONS), None)
        lines.append(AuditLine(text=text, indent=float(indent), bar="B" in flags, icon=icon))
    return lines


def requirements(parsed):
    return {r.name: r for r in parsed.requirements}


def test_student_fields_and_no_personal_data():
    parsed = parse_lines(fake_lines())
    assert parsed.major == "BS Imaginary Zoology"
    assert parsed.catalog_year == "2024"
    assert parsed.classification == "Junior"
    assert parsed.has_hold is True
    # Course Totals (68 here) wins over the header's Degree Hours (64).
    assert (parsed.total_hours_earned, parsed.total_hours_needed) == (Decimal("68.00"), Decimal("120.00"))
    # Nothing personal anywhere in what was parsed: name, ID, address, phone, advisor, GPA, hold text.
    everything = repr(parsed)
    for private in ("Fakerson", "Testy", "999000111", "Imaginary Lane", "Nowhere", "555",
                    "Mentor", "3.95", "3.9000", "Library Fine"):
        assert private not in everything


def test_every_requirement_block_met_or_not_once():
    parsed = parse_lines(fake_lines())
    names = [r.name for r in parsed.requirements]
    assert names == [
        "General Education", "English Composition", "Fine Arts/Humanities", "Literature", "Fine Arts Choice",
        "Primary AIM: Imaginary Zoology", "Zoology", "Zoology I/Lab", "UL Zoology Electives", "Mathematics",
        "Select 5 hours:", "Select 3-5 hours:", "Physics", "University Requirements", "Freshman Seminar",
        "University Residency",
    ]  # headers repeated on pages 2 and 3 are merged; Course Totals is not a requirement
    reqs = requirements(parsed)
    assert reqs["General Education"].status == "met"
    assert reqs["General Education"].hours_earned == Decimal("12.00")
    assert reqs["General Education"].notes == [
        "General Education Requirements (12 hours)", "3 hours of Mathematics are included in the major.",
    ]  # the repeat at the top of page 2 is not added twice
    assert reqs["Literature"].parent_name == "Fine Arts/Humanities"
    assert reqs["Fine Arts/Humanities"].parent_name == "General Education"
    assert reqs["Fine Arts/Humanities"].rule == "all"  # "Select 3 hours of X and 3 hours of Y" is a description
    assert (reqs["Literature"].rule, reqs["Literature"].hours_required) == ("choose_hours", Decimal(3))
    assert reqs["Literature"].course_options == ["ENGL 2213", "ENGL 2223"]
    assert reqs["Fine Arts Choice"].course_options == ["ART 2013"]
    assert "- 3 hours of Foreign Language" in reqs["Fine Arts Choice"].notes
    # Page 3 starts with the block's repeated summary and description but no header; the
    # bar after them still belongs to Mathematics, where page 2 left off.
    assert reqs["Select 3-5 hours:"].parent_name == "Mathematics"
    assert reqs["Select 3-5 hours:"].hours_required == Decimal(3)
    assert reqs["Primary AIM: Imaginary Zoology"].notes == ["Imaginary Zoology Major Requirements"]
    assert reqs["Physics"].course_options == ["PHYS 2003", "PHYS 2001"]
    assert reqs["University Residency"].status == "not_met"


def test_not_met_and_in_progress_requirements():
    reqs = requirements(parse_lines(fake_lines()))
    zoology = reqs["Zoology"]
    assert zoology.status == "in_progress"  # not met, with a course under way
    assert "ZOO 4932" in zoology.course_options  # still needed
    assert reqs["Zoology I/Lab"].course_options == ["ZOO 2103", "ZOO 2101"]
    assert reqs["Zoology I/Lab"].hours_earned == Decimal("4.00")
    assert reqs["UL Zoology Electives"].status == "in_progress"
    assert reqs["Select 3-5 hours:"].status == "not_met"
    assert reqs["Primary AIM: Imaginary Zoology"].hours_earned == Decimal("30.00")


def test_course_lines():
    courses = {(c.course_code, c.requirement_name): c for c in parse_lines(fake_lines()).courses}
    transfer = courses[("ENGL 1113", "English Composition")]  # counted as SAU's ENGL 1113
    assert (transfer.status, transfer.grade, transfer.credits, transfer.term, transfer.transfer) == (
        "completed", "A", Decimal("3.00"), "2022 3T", True,
    )
    d_grade = courses[("ZOO 3103", "Zoology")]
    assert (d_grade.grade, d_grade.credits) == ("D", Decimal("3.00"))
    lab = courses[("ZOO 2101", "Zoology I/Lab")]
    assert (lab.grade, lab.credits, lab.term) == ("A", Decimal("1.00"), "2023 1S")
    assert courses[("ART 2013", "Fine Arts Choice")].grade == "B"
    in_progress = courses[("ZOO 4143", "Zoology")]
    assert (in_progress.status, in_progress.credits, in_progress.term, in_progress.grade) == (
        "in_progress", Decimal("3.00"), "AY 2026-2027 - Fall", None,
    )
    cumulative = courses[("ZOO 3903", "UL Zoology Electives")]
    assert cumulative.status == "in_progress"
    assert ("ZOO 4932", "Zoology") not in courses  # needed, not taken


def test_nonapplied_coursework_has_no_requirement():
    courses = parse_lines(fake_lines()).courses
    nonapplied = {c.course_code: c for c in courses if c.requirement_name is None}
    assert set(nonapplied) == {"HIST 2023", "MATH 1023"}  # transfer MATH1053 counts as MATH 1023
    assert nonapplied["MATH 1023"].transfer is True
    assert len(courses) == 17
