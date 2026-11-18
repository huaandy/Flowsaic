"""Connect mySAU for an existing Flowsaic student from the command line.

Run from backend/:
    uv run python ..\\db\\scripts\\connect_mysau.py --student-id <uuid> --fetch sections audit

A Chromium window opens. Sign in yourself (Microsoft + Duo if asked); you have 5 minutes.
Then the script exports the course schedule and/or downloads, reads and saves the degree
audit. Nothing you type is seen or stored by the script; the audit PDF is never saved.
Each kind is recorded in refresh_runs. Same code as POST /connect/mysau.
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.db import SessionLocal  # noqa: E402
from app.models import RefreshRun  # noqa: E402
from app.mysau.audit_store import StudentNotFound  # noqa: E402
from app.mysau.run import ConnectAlreadyRunning, start_connect  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--student-id", required=True, type=uuid.UUID)
    parser.add_argument("--fetch", nargs="+", choices=["sections", "audit"], default=["sections", "audit"])
    args = parser.parse_args()

    try:
        run_ids = start_connect(args.student_id, args.fetch, wait=True, status=lambda s: print(f"  {s}"))
    except StudentNotFound:
        sys.exit("No Flowsaic student with that id. The audit attaches to an existing student only.")
    except ConnectAlreadyRunning:
        sys.exit("A connect is already running.")

    failed = False
    with SessionLocal() as session:
        for kind, run_id in run_ids.items():
            run = session.get(RefreshRun, run_id)
            detail = f"{run.rows_changed} rows" if run.status == "ok" else run.error
            print(f"{kind}: {run.status} ({detail})  refresh_run {run_id}")
            failed |= run.status != "ok"
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
