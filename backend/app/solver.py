"""find_schedules: section combinations that fit a student's constraints. A tool for Flow
(the AI advisor) so it never has to work out time conflicts or combinations itself.

Input:
- must: course codes that have to be in the schedule.
- optional: course codes that may be added, best first (e.g. required, then choices,
  then electives), until the credits reach the target.
- constraints (all optional). Hard: unavailable blocks, earliest start, latest end, days off,
  instructors to avoid, open seats only, no online. Soft (ranking only): preferred time of
  day, lunch break, preferred instructors, fewer days on campus, fewer full sections.
Output: up to `limit` schedules (one section per course, no time overlaps), best first,
plus the must courses that can't be scheduled and why.

Every schedule still goes through the checker before anyone sees it; the solver only
avoids time overlaps and the hard constraints.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import time

from sqlalchemy import select

from app.checker import SectionInfo, overlap, section_info
from app.db import SessionLocal
from app.models import Course, Section

NODE_BUDGET = 40_000  # search steps before we stop looking for more combinations
KEEP = 400  # complete schedules kept for ranking
MORNING_END, AFTERNOON_END = time(12, 0), time(17, 0)


@dataclass
class Block:
    days: str
    start: time
    end: time


@dataclass
class Constraints:
    unavailable: list[Block] = field(default_factory=list)
    earliest_start: time | None = None
    latest_end: time | None = None
    days_off: str = ""
    avoid_instructors: list[str] = field(default_factory=list)
    preferred_instructors: list[str] = field(default_factory=list)
    preferred_time: str | None = None  # morning | afternoon | evening
    lunch: Block | None = None  # soft: days ignored, every meeting day
    open_seats_only: bool = False
    allow_online: bool = True
    min_credits: float | None = None
    max_credits: float = 18


def _instructor_matches(instructor: str, names: list[str]) -> bool:
    text = instructor.lower()
    return any(name.strip() and re.search(r"\b" + re.escape(name.strip().lower()) + r"\b", text) for name in names)


def why_not(section: SectionInfo, c: Constraints) -> str | None:
    """The hard constraint a section breaks, or None if it fits."""
    if c.open_seats_only and section.capacity and section.seats_open == 0:
        return "full"
    if c.avoid_instructors and _instructor_matches(section.instructor, c.avoid_instructors):
        return "instructor to avoid"
    if not section.meets:
        return None if c.allow_online else "online or TBA"
    if set(section.days) & set(c.days_off.upper()):
        return "meets on a day off"
    if c.earliest_start and section.start < c.earliest_start:
        return "starts too early"
    if c.latest_end and section.end > c.latest_end:
        return "ends too late"
    for block in c.unavailable:
        if set(section.days) & set(block.days.upper()) and section.start < block.end and block.start < section.end:
            return "meets during unavailable time"
    return None


def score(sections: list[SectionInfo], c: Constraints, priority: dict[str, int]) -> float:
    """Higher is better. Soft preferences only."""
    total = 0.0
    days_used: set[str] = set()
    for s in sections:
        total -= priority.get(s.code, 0) * 0.5  # earlier optional courses rank higher
        if s.capacity and s.seats_open == 0:
            total -= 3
        if c.preferred_instructors and _instructor_matches(s.instructor, c.preferred_instructors):
            total += 2
        if not s.meets:
            continue
        days_used |= set(s.days)
        if c.preferred_time == "morning" and s.start < MORNING_END:
            total += 1
        elif c.preferred_time == "afternoon" and MORNING_END <= s.start < AFTERNOON_END:
            total += 1
        elif c.preferred_time == "evening" and s.start >= AFTERNOON_END:
            total += 1
        elif c.preferred_time:
            total -= 1
        if c.lunch and s.start < c.lunch.end and c.lunch.start < s.end:
            total -= 1.5
    total -= len(days_used) * 0.3
    return total


def search(
    must: list[str],
    optional: list[str],
    sections_by_course: dict[str, list[SectionInfo]],
    constraints: Constraints,
    limit: int = 5,
) -> dict:
    """Pure: the combinations, best first, and the must courses that can't be placed."""
    viable: dict[str, list[SectionInfo]] = {}
    unschedulable: list[dict] = []
    for code in list(dict.fromkeys(must + optional)):
        offered = sections_by_course.get(code, [])
        fits = [s for s in offered if why_not(s, constraints) is None]
        if fits:
            viable[code] = fits
        elif code in must:
            reasons = sorted({why_not(s, constraints) for s in offered})
            unschedulable.append({"code": code, "reason": "not offered this term" if not offered
                                  else "no section fits: " + ", ".join(reasons)})
    if unschedulable:
        return {"schedules": [], "unschedulable": unschedulable, "complete": True, "message": None}

    must_codes = sorted(dict.fromkeys(must), key=lambda code: len(viable[code]))  # fewest choices first
    optional_codes = [code for code in dict.fromkeys(optional) if code in viable and code not in must]
    priority = {code: i for i, code in enumerate(optional_codes)}
    min_credits = constraints.min_credits

    found: list[tuple[float, list[SectionInfo]]] = []
    steps = 0

    def credits(chosen: list[SectionInfo]) -> float:
        return sum(s.credits for s in chosen)

    def fits_with(section: SectionInfo, chosen: list[SectionInfo]) -> bool:
        return all(overlap(section, other) is None for other in chosen)

    def record(chosen: list[SectionInfo]) -> None:
        total = credits(chosen)
        if total > constraints.max_credits or (min_credits is not None and total < min_credits):
            return
        found.append((score(chosen, constraints, priority), list(chosen)))

    def place_must(i: int, chosen: list[SectionInfo]) -> None:
        nonlocal steps
        if steps > NODE_BUDGET or len(found) >= KEEP:
            return
        if i == len(must_codes):
            add_optional(0, chosen)
            return
        for section in viable[must_codes[i]]:
            steps += 1
            if fits_with(section, chosen):
                chosen.append(section)
                place_must(i + 1, chosen)
                chosen.pop()

    def add_optional(i: int, chosen: list[SectionInfo]) -> None:
        nonlocal steps
        if steps > NODE_BUDGET or len(found) >= KEEP:
            return
        total = credits(chosen)
        reached = min_credits is None or total >= min_credits
        if i == len(optional_codes) or (reached and min_credits is not None):
            record(chosen)
            return
        code = optional_codes[i]
        for section in viable[code]:
            steps += 1
            if total + section.credits <= constraints.max_credits and fits_with(section, chosen):
                chosen.append(section)
                add_optional(i + 1, chosen)
                chosen.pop()
        add_optional(i + 1, chosen)  # or skip this course

    place_must(0, [])

    # Best first; one schedule per distinct set of sections.
    seen: set[frozenset] = set()
    schedules = []
    for value, chosen in sorted(found, key=lambda pair: -pair[0]):
        key = frozenset(s.id for s in chosen)
        if key in seen:
            continue
        seen.add(key)
        schedules.append({"sections": chosen, "credits": credits(chosen), "score": round(value, 2)})
        if len(schedules) >= limit:
            break
    message = None
    if not schedules:
        must_credits = sum(min(s.credits for s in viable[code]) for code in must_codes)
        message = (f"the required courses alone are {must_credits:g} credits, over the {constraints.max_credits:g} limit"
                   if must_credits > constraints.max_credits
                   else "no combination fits without a time overlap" + (
                       f" and reaches {min_credits:g} credits" if min_credits is not None else ""))
    return {"schedules": schedules, "unschedulable": [], "complete": steps <= NODE_BUDGET, "message": message}


def load_term_sections(course_codes: list[str], term_id: uuid.UUID) -> dict[str, list[SectionInfo]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Section, Course).join(Course, Course.id == Section.course_id)
            .where(Course.code.in_(course_codes), Section.term_id == term_id, Section.active.is_(True))
            .order_by(Course.code, Section.section_number)
        ).all()
    by_course: dict[str, list[SectionInfo]] = {}
    for section, course in rows:
        by_course.setdefault(course.code, []).append(section_info(section, course))
    return by_course


def find_schedules(must: list[str], optional: list[str], constraints: Constraints, term_id: uuid.UUID,
                   limit: int = 5) -> dict:
    sections = load_term_sections(list(dict.fromkeys(must + optional)), term_id)
    return search(must, optional, sections, constraints, limit)


def load_offered_codes(term_id: uuid.UUID) -> list[str]:
    """Course codes with an active section in the term."""
    with SessionLocal() as session:
        return list(session.scalars(
            select(Course.code).join(Section, Section.course_id == Course.id)
            .where(Section.term_id == term_id, Section.active.is_(True)).distinct()
        ))
