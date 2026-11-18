"""Load data/course_info.csv into courses and course_prereqs.

Run from backend/:  uv run python ..\\db\\scripts\\load_course_info.py [path-to-csv]

Re-running updates rows instead of duplicating them:
- courses are matched on code; title, description and other_requirements are updated.
  department and credits are left alone (they come from import_sections.py).
- each course's prereq rows are replaced with what the file says now.
Bad rows are printed and skipped, never guessed.
The work is done by backend/app/course_load.py, shared with the public data refresh.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import REPO_DIR  # noqa: E402
from app.course_load import load_course_info_csv  # noqa: E402

DEFAULT_PATH = REPO_DIR / "data" / "course_info.csv"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    try:
        result = load_course_info_csv(path)
    except ValueError as error:
        sys.exit(str(error))

    print(f"File: {path}")
    print(f"Rows read:                  {result.rows_read}")
    print(
        f"Courses loaded:             {result.courses}  "
        f"({result.inserted} new, {result.courses - result.inserted} updated)"
    )
    print(f"  with a description:       {result.with_description}")
    print(f"  without a description:    {result.courses - result.with_description}")
    print(f"Courses with prereqs:       {result.courses_with_prereqs}")
    print(f"Prereq rows loaded:         {result.prereq_rows}")
    print(f"Courses in the table now:   {result.table_total}")
    print(f"Rejected rows:              {len(result.rejected)}")
    for message in result.rejected:
        print(f"  {message}")


if __name__ == "__main__":
    main()
