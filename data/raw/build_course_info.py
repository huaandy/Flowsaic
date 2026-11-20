"""Rebuild data/course_info.csv and data/course_info_needs_review.csv from the saved raw
catalog scrape, offline (no requests to SAU).

    python build_course_info.py                      # from data/raw/, plain Python 3.12+
    python build_course_info.py other_raw_file.json

Since Nov 20 this is a thin wrapper: the rules live in backend/app/catalog/course_build.py,
the same code db/scripts/scrape_course_info.py uses, so the two can never drift apart.
data/course_prereq_overrides.csv (reviewed hand fixes) is applied last, so a hand fix is
never lost by a rebuild. To load the result into the database, run
db/scripts/load_course_info.py (or scrape_course_info.py --offline, which does both).
"""

import collections
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA.parent / "backend"))

from app.catalog.course_build import apply_overrides, build_rows, load_overrides, write_csvs  # noqa: E402

raw_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sau_catalog_2026_27_raw.json")
rows = build_rows(json.loads(raw_path.read_text(encoding="utf-8")))
overrides, problems = load_overrides(DATA / "course_prereq_overrides.csv")
rows, unknown = apply_overrides(rows, overrides)
for problem in problems + unknown:
    print(f"override not applied: {problem}")
write_csvs(rows, DATA / "course_info.csv", DATA / "course_info_needs_review.csv")

review = [r for r in rows if r["needs_review"]]
print("courses", len(rows), "| with description", sum(1 for r in rows if r["description"]),
      "| with prereq text", sum(1 for r in rows if r["prereq_text"]),
      "| with course prereqs", sum(1 for r in rows if r["prereqs"]),
      "| OR groups", sum(1 for r in rows if "|" in r["prereqs"]),
      "| alternative sets", sum(1 for r in rows if "+" in r["prereqs"]),
      "| overrides applied", len(overrides) - len(unknown),
      "| needs_review", len(review))
print(collections.Counter(x for r in review for x in r["needs_review"].split("; ")))
