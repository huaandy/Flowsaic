"""Course schedule export parsing. A small fake CSV; no database."""

from datetime import time

import pytest

from app.mysau.sections_import import ExportNotUnderstood, parse_export, read_export

HEADER = (
    "course_section,title,term,department,start_time,end_time,days,campus,building,room,"
    "instructor,level,credits,enrolled,capacity,concurrent\n"
)
ROWS = [
    "ZOO 2103 001,Zoology I,2026-2027 - Spring,Dept of Zoology,09:00:AM,09:50:AM,M W F,Main,SCI,101,Pat Doe,UG,3.0,10,30,No",
    "ZOO 2101 002L,Zoology I Lab,2026-2027 - Spring,Dept of Zoology,01:30:PM,03:20:PM,T,Main,SCI,102,,UG,1.0,12,12,No",
    "ZOO2103 029,Zoology I,2026-2027 - Spring,Dept of Zoology,,,,Online,,,Pat Doe,UG,3.0,5,25,No",
    # The same section twice (lecture + an exam slot): the row with more days is kept.
    "ZOO 3103 001,Dragons,2026-2027 - Spring,Dept of Zoology,06:00:PM,07:00:PM,R,Main,SCI,1,Lee Roe,UG,3.0,1,20,No",
    "ZOO 3103 001,Dragons,2026-2027 - Spring,Dept of Zoology,10:00:AM,11:15:AM,T R,Main,SCI,1,Lee Roe,UG,3.0,1,20,No",
    "ZOO 4103 001,CANCELED Unicorns,2026-2027 - Spring,Dept of Zoology,,,,Main,,,,UG,3.0,0,0,No",
    "ZOO 4203 001,Bad Time,2026-2027 - Spring,Dept of Zoology,25:00:PM,26:00:PM,M,Main,,,,UG,3.0,0,0,No",
]


def export(*rows: str) -> bytes:
    return ("﻿" + HEADER + "\n".join(rows) + "\n").encode("utf-8")


def test_parse_export_normalizes_like_import_sections():
    parsed = parse_export(read_export(export(*ROWS)))
    assert parsed.rows_read == 7
    assert parsed.terms == {"2026-2027 - Spring": "Spring 2027"}
    by_key = {(row["course_code"], row["section_number"]): row for row in parsed.sections}
    assert set(by_key) == {("ZOO 2103", "001"), ("ZOO 2101", "002L"), ("ZOO 2103", "029"), ("ZOO 3103", "001")}

    lecture = by_key[("ZOO 2103", "001")]
    assert (lecture["days"], lecture["start_time"], lecture["end_time"]) == ("MWF", time(9), time(9, 50))
    assert by_key[("ZOO 2101", "002L")]["instructor"] == "Staff"  # blank instructor
    online = by_key[("ZOO 2103", "029")]  # "ZOO2103" gets its space back
    assert (online["days"], online["start_time"], online["location"]) == (None, None, "Online")

    dragons = by_key[("ZOO 3103", "001")]
    assert (dragons["days"], dragons["start_time"]) == ("TR", time(10))
    assert len(parsed.extra_meetings) == 1

    assert len(parsed.canceled) == 1 and "CANCELED Unicorns" in parsed.canceled[0]
    assert len(parsed.rejected) == 1 and "time not understood" in parsed.rejected[0]
    assert parsed.courses["ZOO 2103"]["credits"] == 3


def test_sections_that_disagree_on_credits_leave_credits_blank():
    rows = [ROWS[0], ROWS[0].replace(" 001,", " 002,").replace(",3.0,", ",4.0,")]
    parsed = parse_export(read_export(export(*rows)))
    assert parsed.credit_conflicts == {"ZOO 2103"}
    assert parsed.courses["ZOO 2103"]["credits"] is None


def test_an_unexpected_file_is_refused():
    with pytest.raises(ExportNotUnderstood, match="missing columns"):
        read_export(b"course_section,name\nZOO 2103 001,Zoology\n")
    with pytest.raises(ExportNotUnderstood, match="16 fields"):
        read_export(b"code,name\nZOO 2103,Zoology\n")
    with pytest.raises(ExportNotUnderstood, match="HTML table"):
        read_export(b"<table><tr><td>ZOO</td></tr></table>")


# mySAU's raw export (Nov 17): no header, no quoting, commas inside titles and departments,
# lab sections written as "001  L", a blank last line.
RAW_EXPORT = (
    "ZOO 2103 001,Zoology I,2026-2027 - Spring,Dept of Zoology, Botany, & Fungi,09:00:AM,09:50:AM,M W F,"
    "Main Campus,Science Hall,101,Pat Doe,UG,3.00,10,30,No\n"
    "ZOO 2101 001  L,Zoology I Lab,2026-2027 - Spring,Dept of Zoology, Botany, & Fungi,01:30:PM,03:20:PM,T,"
    "Main Campus,Science Hall,102,Pat Doe,UG,1.00,12,12,No\n"
    "ZOO 4003 029,Dragons, Wyverns, & Drakes,2026-2027 - Spring,Dept of Zoology, Botany, & Fungi,,,,"
    "Online,Online,ONLIN,Lee Roe,UG,3.00,5,25,No\n"
    "ZOO 4103 001,Broken row,with too few fields\n"
    "\n"
).encode()


def test_raw_mysau_export():
    parsed = parse_export(read_export(RAW_EXPORT))
    by_key = {(row["course_code"], row["section_number"]): row for row in parsed.sections}
    assert set(by_key) == {("ZOO 2103", "001"), ("ZOO 2101", "001L"), ("ZOO 4003", "029")}
    lecture = by_key[("ZOO 2103", "001")]
    assert lecture["department"] == "Dept of Zoology, Botany, & Fungi"
    assert (lecture["days"], lecture["start_time"], lecture["credits"], lecture["capacity"]) == ("MWF", time(9), 3, 30)
    assert by_key[("ZOO 4003", "029")]["title"] == "Dragons, Wyverns, & Drakes"
    assert by_key[("ZOO 4003", "029")]["days"] is None  # online
    assert parsed.rejected == ["line 4: 'ZOO 4103 001,Broken row,with too few fie' '' - row does not have the export's 16 fields"]
