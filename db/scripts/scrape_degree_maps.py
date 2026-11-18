"""Scrape every undergraduate degree map and load degree_plans, requirement_groups and
requirement_courses.

Run from backend/:
    uv run python ..\\db\\scripts\\scrape_degree_maps.py                  # every program (slow, see below)
    uv run python ..\\db\\scripts\\scrape_degree_maps.py --only computer-science
    uv run python ..\\db\\scripts\\scrape_degree_maps.py --offline        # re-parse saved pages, no requests
    uv run python ..\\db\\scripts\\scrape_degree_maps.py --show "Computer Science, BS"

Source: www.saumag.edu/academics/program/<slug>/ (the catalog's own program pages are
behind bot protection; see backend/app/catalog/degree_maps.py). One page every
DEGREE_MAPS_DELAY_SECONDS (30 s by default), so all ~150 pages take a bit over an hour.
The general education page is fetched once per run and copied into each plan's gen ed block.
Re-running replaces each plan's requirement tree; plan ids stay the same.
Each run is recorded in refresh_runs (kind 'degree_maps').
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.catalog.degree_maps import plan_tree, refresh_degree_maps  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.refresh import finish_run, short_error, start_run  # noqa: E402


def print_tree(groups: list[dict], indent: int = 0) -> None:
    for group in groups:
        rule = group["rule"] if group["rule"] == "all" else f"choose {group['hours_required']} hours"
        print(f"{'    ' * indent}- {group['name']}  [{rule}]")
        if group["courses"]:
            print(f"{'    ' * indent}    courses: {', '.join(group['courses'])}")
        if group["note"]:
            print(f"{'    ' * indent}    note: {group['note']}")
        print_tree(group["children"], indent + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", metavar="SLUG", help="only these program page slugs")
    parser.add_argument("--limit", type=int, help="only the first N program pages")
    parser.add_argument("--offline", action="store_true", help="re-parse saved pages, fetch nothing")
    parser.add_argument("--show", metavar="NAME", help="print a loaded plan's tree and exit")
    parser.add_argument("--year", default="2026-2027", help="catalog year for --show")
    args = parser.parse_args()

    if args.show:
        year = args.year
        tree = plan_tree(args.show, year)
        if not tree:
            sys.exit(f"No plan named {args.show!r} for {year}.")
        print(f"{args.show} ({year})")
        print_tree(tree)
        return

    if not args.offline:
        delay = get_settings().degree_maps_delay_seconds
        print(f"Fetching from www.saumag.edu, one page every {delay:.0f} s. Ctrl+C to stop.")
    # Only a full run is recorded: a partial one must not look like a fresh refresh to the
    # startup check (which skips the refresh when the last good run is under 7 days old).
    partial = bool(args.only or args.limit is not None)
    run_id = None if partial else start_run("degree_maps")
    if run_id:
        print(f"refresh_run {run_id}")
    try:
        loaded = refresh_degree_maps(offline=args.offline, only=args.only, limit=args.limit, log_line=print)
    except KeyboardInterrupt:
        if run_id:
            finish_run(run_id, ok=False, error="stopped by hand")
        sys.exit("Stopped. Plans loaded so far are kept; run again to redo the rest.")
    except Exception as error:
        if run_id:
            finish_run(run_id, ok=False, error=short_error(error))
        sys.exit(f"Failed: {short_error(error)}")
    if run_id:
        finish_run(run_id, ok=True, rows_changed=loaded)
    print(f"Done. Plans loaded: {loaded}")


if __name__ == "__main__":
    main()
