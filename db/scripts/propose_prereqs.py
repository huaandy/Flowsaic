"""Ask Gemini, once and offline, to propose structured prereqs for the wording the parser
can't read. Writes data/course_prereq_proposals.csv for a person to review.

Run from backend/:
    uv run python ..\\db\\scripts\\propose_prereqs.py --dry-run      # list the courses, no Gemini call
    uv run python ..\\db\\scripts\\propose_prereqs.py                # every needs_review + pair course
    uv run python ..\\db\\scripts\\propose_prereqs.py --only "HS 4433" "MATH 2124"

Nothing is used until a person copies a reviewed row into data/course_prereq_overrides.csv
(code, prereqs, other_requirements, reviewed_by = their name, note) and rebuilds:
    uv run python ..\\db\\scripts\\scrape_course_info.py --offline
Only public catalog wording is sent to Gemini (code, title, prerequisite text). Batches of 20,
so a full pass is about 7 calls. Needs GEMINI_API_KEY and GEMINI_MODEL in .env.
The logic is in backend/app/catalog/prereq_proposals.py.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.catalog.prereq_proposals import propose, select_rows, write_proposals  # noqa: E402
from app.config import REPO_DIR, get_settings  # noqa: E402

COURSE_INFO = REPO_DIR / "data" / "course_info.csv"
PROPOSALS = REPO_DIR / "data" / "course_prereq_proposals.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", metavar="CODE", help="just these course codes")
    parser.add_argument("--limit", type=int, help="at most this many courses")
    parser.add_argument("--dry-run", action="store_true", help="list the courses; call nothing")
    args = parser.parse_args()

    rows = select_rows(COURSE_INFO, set(args.only) if args.only else None)
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} courses to propose")
    if args.dry_run:
        for row in rows:
            print(f"  {row['code']}: {row['prereq_text'][:100]}")
        return
    settings = get_settings()
    if not settings.gemini_api_key or not settings.gemini_model:
        sys.exit("GEMINI_API_KEY and GEMINI_MODEL must be set in .env.")
    from app.embeddings import get_client

    proposals = propose(rows, get_client(), settings.gemini_model)
    write_proposals(proposals, PROPOSALS)
    usable = sum(1 for p in proposals if p["valid"] == "yes")
    print(f"Wrote {PROPOSALS} ({usable} of {len(proposals)} pass the code checks). Review them; copy the "
          "ones you agree with into data/course_prereq_overrides.csv with your name in reviewed_by.")


if __name__ == "__main__":
    main()
