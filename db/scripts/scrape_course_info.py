"""Scrape course descriptions from SAU's public catalog, rebuild course_info.csv, load it,
and re-embed only the courses whose text changed.

Run from backend/:
    uv run python ..\\db\\scripts\\scrape_course_info.py              # rebuild + load from the raw file
    uv run python ..\\db\\scripts\\scrape_course_info.py --limit 5    # fetch 5 stale pages first

Decided Nov 17: course text changes once a catalog year, so by default nothing is
fetched and the saved raw file (data/raw/sau_catalog_2026_27_raw.json) is reused. To
crawl again (a new catalog year), set COURSE_INFO_CRAWL=true in backend/.env or pass
--limit. The catalog asks for 120 seconds between requests (robots.txt), so a full pass
over ~1,900 courses takes about 63 hours. Progress is saved as it goes; stop it any time and
run it again to continue. Pages fetched in the last 7 days are skipped.
Each run is recorded in refresh_runs (kind 'course_info').
The work is done by backend/app/catalog/course_pages.py, shared with POST /data/refresh/public.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.catalog.course_pages import refresh_course_info  # noqa: E402
from app.refresh import finish_run, short_error, start_run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="fetch at most this many pages")
    parser.add_argument("--offline", action="store_true", help="fetch nothing; rebuild from the raw file")
    parser.add_argument("--no-load", action="store_true", help="write the CSVs but do not load or embed")
    args = parser.parse_args()

    # Recorded even with --limit: course runs only ever fetch stale pages, so a limited
    # run is still a valid refresh of what it covers.
    run_id = start_run("course_info")
    print(f"refresh_run {run_id}")
    try:
        changed = refresh_course_info(
            limit=0 if args.offline else args.limit,
            load_and_embed=not args.no_load,
            log_line=print,
        )
    except KeyboardInterrupt:
        finish_run(run_id, ok=False, error="stopped by hand; progress saved")
        sys.exit("Stopped. Progress is saved; run again to continue.")
    except Exception as error:
        finish_run(run_id, ok=False, error=short_error(error))
        sys.exit(f"Failed: {short_error(error)}")
    finish_run(run_id, ok=True, rows_changed=changed)
    print(f"Done. course_info.csv rows changed: {changed}")


if __name__ == "__main__":
    main()
