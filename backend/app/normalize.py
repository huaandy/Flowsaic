"""Pure helpers that turn SAU export text into contract formats.

Every helper raises ValueError with a plain reason when the input is not understood,
so the import scripts can print the row and skip it. Nothing here guesses.
"""

import re
from datetime import time

DAY_ORDER = "MTWRFSU"  # R = Thursday, U = Sunday

COURSE_CODE_RE = re.compile(r"^[A-Z]+(?: [A-Z]+)* \d{4,5}$")  # CSCI 3103, E ED 4173, ESL 02230
SECTION_NUMBER_RE = re.compile(r"^\d{3}[A-Z]?$")  # 001, 002L, 001H
EXPORT_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(AM|PM)$")  # 09:00:AM
TERM_RE = re.compile(r"^(\d{4})-(\d{4}) - (Fall|Spring)$")  # 2026-2027 - Spring


def normalize_course_code(raw: str) -> str:
    """'SCM6003' -> 'SCM 6003'. 'CSCI  3103' -> 'CSCI 3103'."""
    code = " ".join(raw.split())
    code = re.sub(r"^([A-Z ]*[A-Z])(\d+)$", r"\1 \2", code)
    if not COURSE_CODE_RE.fullmatch(code):
        raise ValueError(f"course code not understood: {raw!r}")
    return code


def split_course_section(raw: str) -> tuple[str, str]:
    """'ACCT 2003 001' -> ('ACCT 2003', '001'). The last token is the section.

    mySAU's raw export writes lab sections as '001  L'; that is section '001L'.
    """
    tokens = raw.split()
    if len(tokens) >= 3 and re.fullmatch(r"[A-Z]", tokens[-1]) and re.fullmatch(r"\d{3}", tokens[-2]):
        tokens = tokens[:-2] + [tokens[-2] + tokens[-1]]
    if len(tokens) < 2:
        raise ValueError(f"course_section has no section number: {raw!r}")
    section_number = tokens[-1]
    if not SECTION_NUMBER_RE.fullmatch(section_number):
        raise ValueError(f"section number not understood: {raw!r}")
    return normalize_course_code(" ".join(tokens[:-1])), section_number


def parse_export_time(raw: str) -> time | None:
    """'09:00:AM' -> 09:00, '01:30:PM' -> 13:30. Blank -> None (online or TBA)."""
    value = raw.strip()
    if not value:
        return None
    match = EXPORT_TIME_RE.fullmatch(value)
    if not match:
        raise ValueError(f"time not understood: {raw!r}")
    hour, minute, half = int(match.group(1)), int(match.group(2)), match.group(3)
    if not 1 <= hour <= 12 or minute > 59:
        raise ValueError(f"time not understood: {raw!r}")
    if half == "AM":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return time(hour, minute)


def normalize_days(raw: str) -> str | None:
    """'M W F' -> 'MWF', 'T RF' -> 'TRF'. Blank -> None (online or TBA)."""
    letters = "".join(raw.split())
    if not letters:
        return None
    if any(letter not in DAY_ORDER for letter in letters) or len(set(letters)) != len(letters):
        raise ValueError(f"days not understood: {raw!r}")
    return "".join(letter for letter in DAY_ORDER if letter in letters)


def parse_credits(raw: str) -> int:
    """'3.0' -> 3. Fractional or blank credits are rejected."""
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"credits not understood: {raw!r}") from None
    if value < 0 or value != int(value):
        raise ValueError(f"credits not understood: {raw!r}")
    return int(value)


def parse_count(raw: str, field: str) -> int:
    """Enrolled / capacity: a whole number, zero or more."""
    value = raw.strip()
    if not value.isdigit():
        raise ValueError(f"{field} not understood: {raw!r}")
    return int(value)


def parse_term(raw: str) -> tuple[str, str]:
    """'2026-2027 - Spring' -> ('2026-2027 - Spring', 'Spring 2027').

    The code is SAU's export text as is. Fall belongs to the first year, Spring to the second.
    """
    value = " ".join(raw.split())
    match = TERM_RE.fullmatch(value)
    if not match:
        raise ValueError(f"term not understood: {raw!r}")
    first_year, second_year, season = match.groups()
    year = first_year if season == "Fall" else second_year
    return value, f"{season} {year}"


def parse_prereqs(raw: str) -> list[list[str]]:
    """'CHEM 3103;MATH 1023|MATH 1053' -> [['CHEM 3103'], ['MATH 1023', 'MATH 1053']].

    ';' separates groups that are all required. '|' separates alternatives inside a group.
    Blank -> [] (no prereqs).
    """
    if not raw.strip():
        return []
    groups: list[list[str]] = []
    for group_text in raw.split(";"):
        options: list[str] = []
        for option_text in group_text.split("|"):
            code = " ".join(option_text.split())
            if not COURSE_CODE_RE.fullmatch(code):
                raise ValueError(f"prereq not understood: {raw!r}")
            if code not in options:
                options.append(code)
        groups.append(options)
    return groups
