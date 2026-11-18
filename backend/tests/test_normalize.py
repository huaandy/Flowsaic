from datetime import time

import pytest

from app.normalize import (
    normalize_course_code,
    normalize_days,
    parse_count,
    parse_credits,
    parse_export_time,
    parse_prereqs,
    parse_term,
    split_course_section,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ACCT 2003 001", ("ACCT 2003", "001")),
        ("BIOL 2071 092L", ("BIOL 2071", "092L")),
        ("HC 4013 001H", ("HC 4013", "001H")),
        ("SCM6003 029", ("SCM 6003", "029")),  # missing space is inserted
        ("E ED 4173 029", ("E ED 4173", "029")),  # two-part prefix
        ("AGED 2012 001  L", ("AGED 2012", "001L")),  # mySAU raw export lab section
    ],
)
def test_split_course_section(raw, expected):
    assert split_course_section(raw) == expected


@pytest.mark.parametrize("raw", ["ACCT 2003", "ACCT 2003 1", "acct 2003 001", "2003 001", ""])
def test_split_course_section_rejects_bad_values(raw):
    with pytest.raises(ValueError):
        split_course_section(raw)


def test_normalize_course_code():
    assert normalize_course_code("SCM6003") == "SCM 6003"
    assert normalize_course_code("CSCI  3103") == "CSCI 3103"
    assert normalize_course_code("ESL 02230") == "ESL 02230"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("09:00:AM", time(9, 0)),
        ("01:30:PM", time(13, 30)),
        ("12:20:PM", time(12, 20)),  # noon hour stays 12
        ("12:05:AM", time(0, 5)),  # midnight hour becomes 00
        ("11:59:PM", time(23, 59)),
        ("", None),
        ("  ", None),
    ],
)
def test_parse_export_time(raw, expected):
    assert parse_export_time(raw) == expected


@pytest.mark.parametrize("raw", ["9:00 AM", "13:00:PM", "09:60:AM", "00:10:AM", "TBA"])
def test_parse_export_time_rejects_bad_values(raw):
    with pytest.raises(ValueError):
        parse_export_time(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("M W F", "MWF"), ("T R", "TR"), ("T RF", "TRF"), ("MTWRF", "MTWRF"), ("F W", "WF"), ("", None)],
)
def test_normalize_days(raw, expected):
    assert normalize_days(raw) == expected


@pytest.mark.parametrize("raw", ["M W X", "Th", "MM", "TBA"])
def test_normalize_days_rejects_bad_values(raw):
    with pytest.raises(ValueError):
        normalize_days(raw)


def test_parse_credits():
    assert parse_credits("3.0") == 3
    assert parse_credits("0.0") == 0
    for bad in ("1.5", "", "three", "-1.0"):
        with pytest.raises(ValueError):
            parse_credits(bad)


def test_parse_count():
    assert parse_count("44", "capacity") == 44
    for bad in ("", "-1", "4.0", "full"):
        with pytest.raises(ValueError):
            parse_count(bad, "capacity")


def test_parse_term():
    assert parse_term("2026-2027 - Spring") == ("2026-2027 - Spring", "Spring 2027")
    assert parse_term("2026-2027 - Fall") == ("2026-2027 - Fall", "Fall 2026")
    for bad in ("Spring 2027", "2026-2027 - Summer I", ""):
        with pytest.raises(ValueError):
            parse_term(bad)


def test_parse_prereqs():
    assert parse_prereqs("") == []
    assert parse_prereqs("PH 2003") == [["PH 2003"]]
    assert parse_prereqs("PH 2003|HCAD 2003") == [["PH 2003", "HCAD 2003"]]
    # CHEM 3103 AND (MATH 1023 OR MATH 1053)
    assert parse_prereqs("CHEM 3103;MATH 1023|MATH 1053") == [
        ["CHEM 3103"],
        ["MATH 1023", "MATH 1053"],
    ]
    for bad in ("CHEM 3103;", "junior standing", "CHEM3103"):
        with pytest.raises(ValueError):
            parse_prereqs(bad)
