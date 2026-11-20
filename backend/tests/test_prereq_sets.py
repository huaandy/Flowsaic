"""Prereq alternative sets (Nov 20): '(PHYS 2103 and PHYS 2101) or (PHYS 2213 and PHYS 2211)'.

The CSV syntax ('+'), the loader's rows (alt_set), the checker, progress (can take,
blocked), Flow's get_course and the reviewed overrides file. No database.
"""


import pytest

from app.catalog.course_build import (
    apply_overrides,
    build_row,
    is_lecture_lab_pair,
    load_overrides,
    pair_alternatives,
    parse_prereq_text,
)
from app.checker import check_schedule
from app.course_load import prereq_table_rows
from app.normalize import option_done, parse_prereq_sets, parse_prereqs, prereq_csv
from app.progress import Offering, can_take, load_prereqs, missing_prereqs
from tests.test_checker import section, student

PHYS = "PHYS 2103+PHYS 2101|PHYS 2213+PHYS 2211"
PHYS_GROUPS = [["PHYS 2103 + PHYS 2101", "PHYS 2213 + PHYS 2211"]]


# --- CSV syntax and the loader ----------------------------------------------------------------

def test_plus_joins_courses_into_one_option():
    assert parse_prereq_sets(PHYS) == [[["PHYS 2103", "PHYS 2101"], ["PHYS 2213", "PHYS 2211"]]]
    assert parse_prereqs(PHYS) == PHYS_GROUPS
    assert prereq_csv(PHYS_GROUPS) == PHYS
    assert parse_prereqs("PHYS 2103 + PHYS 2101 ; MATH 1023") == [["PHYS 2103 + PHYS 2101"], ["MATH 1023"]]
    for bad in ("PHYS 2103+", "+PHYS 2101", "PHYS 2103+junior standing"):
        with pytest.raises(ValueError):
            parse_prereq_sets(bad)


def test_old_csv_syntax_loads_the_same_rows_as_before():
    # Before Nov 20 every row of a group was its own alternative: one alt_set each.
    rows = prereq_table_rows("CHEM 3203", parse_prereq_sets("CHEM 3103;MATH 1023|MATH 1053"))
    assert [(r["option_group"], r["alt_set"], r["requires_code"]) for r in rows] == [
        (1, 1, "CHEM 3103"), (2, 1, "MATH 1023"), (2, 2, "MATH 1053")]


def test_a_set_shares_one_alt_set():
    rows = prereq_table_rows("ENGR 2033", parse_prereq_sets(PHYS))
    assert [(r["option_group"], r["alt_set"], r["requires_code"]) for r in rows] == [
        (1, 1, "PHYS 2103"), (1, 1, "PHYS 2101"), (1, 2, "PHYS 2213"), (1, 2, "PHYS 2211")]


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query):
        return iter(self.rows)


def test_load_prereqs_rebuilds_options_lecture_first():
    rows = [("ENGR 2033", 1, 2, "PHYS 2211"), ("ENGR 2033", 1, 1, "PHYS 2101"), ("ENGR 2033", 1, 2, "PHYS 2213"),
            ("ENGR 2033", 1, 1, "PHYS 2103"), ("ENGR 2033", 2, 1, "MATH 2125"), ("ENGR 2033", 2, 2, "MATH 2124")]
    assert load_prereqs(FakeSession(rows)) == {
        "ENGR 2033": [["PHYS 2103 + PHYS 2101", "PHYS 2213 + PHYS 2211"], ["MATH 2125", "MATH 2124"]]}


# --- checking ---------------------------------------------------------------------------------

def test_option_done_needs_every_course_of_a_set():
    assert option_done("PHYS 2103 + PHYS 2101", {"PHYS 2103": 3}, {"PHYS 2101": 1})  # one passed, one in progress
    assert not option_done("PHYS 2103 + PHYS 2101", {"PHYS 2103": 3}, {})
    assert option_done("MATH 1023", {"MATH 1023": 3})


def test_checker_wants_a_whole_lecture_lab_pair():
    prereqs = {"ENGR 2033": PHYS_GROUPS}
    sections = [section("ENGR 2033")]
    # The old encoding blocked a student with PHYS 2103 + 2101 because PHYS 2211 was a group of its own.
    assert check_schedule(sections, student(passed=["PHYS 2103", "PHYS 2101"], prereqs=prereqs))["conflicts"] == []
    assert check_schedule(sections, student(passed=["PHYS 2213"], in_progress=["PHYS 2211"], prereqs=prereqs))["conflicts"] == []
    # A lecture from one pair and the lab from the other is not a pair.
    result = check_schedule(sections, student(passed=["PHYS 2103", "PHYS 2211"], prereqs=prereqs))
    assert [(c["code"], c["message"]) for c in result["conflicts"]] == [
        ("missing_prereq", "ENGR 2033 needs PHYS 2103 + PHYS 2101 or PHYS 2213 + PHYS 2211 (passed or in progress)")]


def test_can_take_and_blocked_use_sets():
    prereqs = {"ENGR 2033": PHYS_GROUPS, "ENGR 3103": PHYS_GROUPS}
    needs = [{"code": "ENGR 2033", "group": "Core", "kind": "required"},
             {"code": "ENGR 3103", "group": "Core", "kind": "required"}]
    offered = {"ENGR 2033": Offering(1, 5), "ENGR 3103": Offering(1, 5)}
    passed = {"PHYS 2213": 3.0, "PHYS 2211": 1.0}
    eligible, blocked = can_take(needs, offered, prereqs, passed, {}, {}, {})
    assert {e["code"] for e in eligible} == {"ENGR 2033", "ENGR 3103"} and blocked == []
    eligible, blocked = can_take(needs, offered, prereqs, {"PHYS 2213": 3.0}, {}, {}, {})
    assert eligible == [] and [b["missing_prereqs"] for b in blocked] == [PHYS_GROUPS, PHYS_GROUPS]
    assert missing_prereqs("ENGR 2033", prereqs, {"PHYS 2213": 3.0}, {}) == PHYS_GROUPS


def test_flow_get_course_reads_sets():
    from app.advisor import AdvisorTools
    from tests.test_advisor import make_data

    data = make_data()
    data.context.prereqs["CSCI 4203"] = [["CSCI 3103 + CSCI 3101", "CSCI 3213"]]
    result = AdvisorTools(data).call("get_course", {"code": "CSCI 4203"})
    assert result["prerequisites"] == "(CSCI 3103 + CSCI 3101 or CSCI 3213)"
    # CSCI 3103 is passed but CSCI 3101 isn't, and CSCI 3213 isn't done: still missing.
    assert result["missing_prerequisites"] == ["CSCI 3103 + CSCI 3101 or CSCI 3213"]
    data.context.passed["CSCI 3101"] = 1.0
    assert AdvisorTools(data).call("get_course", {"code": "CSCI 4203"})["missing_prerequisites"] == []


# --- the parser -------------------------------------------------------------------------------

def test_lecture_lab_pair_rule():
    assert is_lecture_lab_pair("PHYS 2103", "PHYS 2101")
    assert is_lecture_lab_pair("AGED 2001", "AGED 2002")
    assert not is_lecture_lab_pair("MATH 1023", "MATH 1033")
    assert not is_lecture_lab_pair("ENGR 3003", "ETEC 3013")
    assert pair_alternatives("ENGR 3003 and ETEC 3013 or ENGR 3023") is None
    assert pair_alternatives("HS 2043 or BIOL 2063 / BIOL 2061") == "HS 2043|BIOL 2063+BIOL 2061"
    assert pair_alternatives("MATH 2124 or MATH 1525") is None  # no pair: the old OR rule handles it


@pytest.mark.parametrize("text, groups", [
    ("CHEM 1013 and CHEM 1011 or CHEM 1023 and CHEM 1021, and PLSC 1003.",
     ["CHEM 1013+CHEM 1011|CHEM 1023+CHEM 1021", "PLSC 1003"]),
    ("ANSC 2002, ANSC 2001, POSC 1003, POSC 1001, and CHEM 1023 and CHEM 1021 or CHEM 1123 and CHEM 1121.",
     ["ANSC 2002", "ANSC 2001", "POSC 1003", "POSC 1001", "CHEM 1023+CHEM 1021|CHEM 1123+CHEM 1121"]),
    ("MATH 2124 or MATH 1525, and PHYS 2003 and PHYS 2001 or PHYS 2203 and PHYS 2201.",
     ["MATH 2124|MATH 1525", "PHYS 2003+PHYS 2001|PHYS 2203+PHYS 2201"]),
    ("ANSC 2013 and either CHEM 1013 and CHEM 1011 or CHEM 1023 and CHEM 1021.",
     ["ANSC 2013", "CHEM 1013+CHEM 1011|CHEM 1023+CHEM 1021"]),
    ("Grades of C or higher in BIOL 1043 /1041 or BIOL 1203 /1201, and grades of C or higher in CHEM 1013 /1011 or CHEM 1023 /1021.",
     ["BIOL 1043+BIOL 1041|BIOL 1203+BIOL 1201", "CHEM 1013+CHEM 1011|CHEM 1023+CHEM 1021"]),
])
def test_pair_wording_from_the_catalog(text, groups):
    found, _other, review = parse_prereq_text(text)
    assert found == groups and review == []


def test_ambiguous_and_or_is_read_as_before():
    # "ETEC 3003 or ENGR 3003 and ETEC 3013 or ENGR 3023": no lecture+lab pairs, so unchanged.
    assert parse_prereq_text("ETEC 3003 or ENGR 3003 and ETEC 3013 or ENGR 3023.")[0] == [
        "ETEC 3003|ENGR 3003", "ETEC 3013|ENGR 3023"]


def test_pairs_or_permission_keep_the_permission_as_a_note():
    row = build_row("BIOL 2061 - Lab", "Prerequisites: Grade of C or higher in CHEM 1013 and CHEM 1011 or CHEM 1023 "
                    "and CHEM 1021, and grade C or higher in BIOL 1043 and BIOL 1041 or BIOL 1203 and BIOL 1201 "
                    "or permission of the department chair.\nLab.")
    assert row["prereqs"] == "CHEM 1013+CHEM 1011|CHEM 1023+CHEM 1021;BIOL 1043+BIOL 1041|BIOL 1203+BIOL 1201"
    assert row["other_requirements"] == "or permission of the department chair"
    assert row["needs_review"] == "course OR non-course alternative"


# --- reviewed overrides -----------------------------------------------------------------------

def write(tmp_path, text):
    path = tmp_path / "course_prereq_overrides.csv"
    path.write_text("code,prereqs,other_requirements,reviewed_by,note\n" + text, encoding="utf-8")
    return path


def test_overrides_apply_last_and_clear_needs_review(tmp_path):
    path = write(tmp_path, "HS 4433,HS 2043+HS 2443,or instructor permission,Victor,checked the catalog\n")
    overrides, problems = load_overrides(path)
    assert problems == []
    row = build_row("HS 4433 - Sports Medicine", "Prerequisites: HS 2043 and HS 2443, or instructor permission.\nX.")
    assert row["prereqs"] == "" and row["needs_review"]
    rows, unknown = apply_overrides([row], overrides)
    assert unknown == []
    assert rows[0]["prereqs"] == "HS 2043+HS 2443"
    assert rows[0]["other_requirements"] == "or instructor permission"
    assert rows[0]["needs_review"] == ""
    assert rows[0]["prereq_text"] == row["prereq_text"]  # the catalog wording is kept


def test_unreviewed_or_bad_overrides_are_never_applied(tmp_path):
    path = write(tmp_path, "HS 4433,HS 2043,,,proposal only\n"
                           "HS 4413,junior standing,,Victor,\n"
                           "CSCI 3103,CSCI 2113,,Victor,\n"
                           "CSCI 3103,CSCI 2103,,Victor,\n"
                           "ZOO 9999,ZOO 1003,,Victor,\n")
    overrides, problems = load_overrides(path)
    assert set(overrides) == {"CSCI 3103", "ZOO 9999"}
    assert len(problems) == 3
    assert any("no reviewed_by" in p for p in problems)
    assert any("listed twice" in p for p in problems)
    _rows, unknown = apply_overrides([build_row("CSCI 3103 - Data Structures", "Text.")], overrides)
    assert unknown == ["ZOO 9999 - not in the catalog"]


def test_missing_overrides_file_is_fine(tmp_path):
    assert load_overrides(tmp_path / "nope.csv") == ({}, [])
