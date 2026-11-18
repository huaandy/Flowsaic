"""Create (or update) the three fake demo students and their completed courses, create
the returning student (user 4, keeps its mySAU data) and reset the new student (user 5).

Run from backend/:  uv run python ..\\db\\scripts\\seed_demo.py
                    uv run python ..\\db\\scripts\\seed_demo.py --clear-returning   # also empty user 4

User 4 holds a real mySAU audit once someone connects it: run with --clear-returning
before a database dump is shared.

Needs the degree plans (scrape_degree_maps.py) and courses (load_course_info.py,
import_sections.py) loaded first. Re-running updates the students in place and replaces
only their source='manual' course rows. The students are defined in
backend/app/demo_seed.py.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.demo_seed import DEMO_PASSWORD, SeedError, seed_demo_students  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clear-returning", action="store_true",
                        help="Also empty user 4 (Returning Student) and the mySAU data on it.")
    args = parser.parse_args()
    try:
        seeded = seed_demo_students(clear_returning=args.clear_returning)
    except SeedError as error:
        sys.exit(f"Nothing was written: {error}")

    for student in seeded:
        print(f"{student.name} <{student.email}>")
        print(f"  {student.plan_name}, {student.classification}, {student.earned_hours} hours earned")
        print(f"  courses: {student.completed} completed, {student.in_progress} in progress")
    print(f"Demo password for all of them: {DEMO_PASSWORD}")
    print("Login page usernames: 1 Alex, 2 Jordan, 3 Sam, 4 Returning Student, 5 New Student (any password for now)")


if __name__ == "__main__":
    main()
