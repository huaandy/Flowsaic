"""The CSV builder (shared by scrape_course_info.py and data/raw/build_course_info.py) must
reproduce the committed CSVs exactly, overrides included."""

import json

import pytest

from app.catalog.course_build import (
    apply_overrides,
    build_row,
    build_rows,
    load_overrides,
    parse_prereq_text,
    write_csvs,
)
from app.config import REPO_DIR

RAW = REPO_DIR / "data" / "raw" / "sau_catalog_2026_27_raw.json"
COURSE_INFO = REPO_DIR / "data" / "course_info.csv"
NEEDS_REVIEW = REPO_DIR / "data" / "course_info_needs_review.csv"


@pytest.mark.skipif(not RAW.exists(), reason="raw catalog scrape not present")
def test_rebuild_from_raw_matches_the_committed_csvs(tmp_path):
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    overrides, problems = load_overrides(REPO_DIR / "data" / "course_prereq_overrides.csv")
    assert problems == []
    rows, unknown = apply_overrides(build_rows(raw), overrides)
    assert unknown == []
    write_csvs(rows, tmp_path / "course_info.csv", tmp_path / "review.csv")
    assert (tmp_path / "course_info.csv").read_bytes() == COURSE_INFO.read_bytes()
    assert (tmp_path / "review.csv").read_bytes() == NEEDS_REVIEW.read_bytes()


def test_and_or_and_other_requirements():
    groups, other, review = parse_prereq_text("CHEM 3103 and MATH 1023 or MATH 1053, instructor permission.")
    assert groups == ["CHEM 3103", "MATH 1023|MATH 1053"]
    assert other == ["instructor permission"]
    assert review == []


def test_mixed_and_or_is_left_blank_for_review():
    row = build_row("HS 4433 - Sports Medicine",
                    "Prerequisites: HS 2043 and HS 2443, or instructor permission.\nLab.")
    assert row["prereqs"] == ""
    assert "and/or mix" in row["needs_review"]


def test_lecture_lab_pairs_become_alternative_sets():
    # Nov 20: was blanked as an and/or mix.
    row = build_row("PHYS 3113 - Advanced Physics Lab",
                    "Prerequisites: PHYS 2103 and PHYS 2101, or PHYS 2213 and PHYS 2211.\nLab.")
    assert row["prereqs"] == "PHYS 2103+PHYS 2101|PHYS 2213+PHYS 2211"
    assert row["needs_review"] == ""


def test_body_lines():
    row = build_row(
        "PHSC 2023 - Physical Sciences",
        "Prerequisites: MATH 1023 or MATH 1053 or higher.\nCorequisites: PHSC 2021 .\n"
        "Elementary physics. 3 hours.\nACTS Course Equivalent: PHSC 1004",
    )
    assert row["code"] == "PHSC 2023"
    assert row["prereqs"] == "MATH 1023|MATH 1053"
    assert row["coreqs"] == "PHSC 2021"
    assert row["description"] == "Elementary physics. 3 hours."


def test_broken_page_is_flagged():
    row = build_row("PLSC 4043\xa0-\xa0Plant Breeding", "")
    assert row["code"] == "PLSC 4043"
    assert row["needs_review"].startswith("SAU detail page is broken")
