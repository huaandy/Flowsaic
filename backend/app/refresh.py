"""refresh_runs bookkeeping and the background public data refresh.

A public refresh runs the degree map scraper, then the course info scraper, one after the
other in a single background thread, so only one request ever goes to the catalog at a time.
Each scraper gets its own refresh_runs row. Startup never waits for any of this.

refresh_runs.error holds a short message we write ourselves, never page content.
"""

import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.config import get_settings
from app.db import SessionLocal
from app.models import RefreshRun

log = logging.getLogger("flowsaic.refresh")

PUBLIC_KINDS = ("degree_maps", "course_info")
ERROR_MAX_LENGTH = 300

_public_lock = threading.Lock()  # held while a public refresh thread is running


class RefreshAlreadyRunning(RuntimeError):
    pass


def short_error(error: BaseException) -> str:
    """A short message for refresh_runs.error: the error type and our own message only."""
    message = str(error).splitlines()[0] if str(error) else ""
    return f"{type(error).__name__}: {message}"[:ERROR_MAX_LENGTH]


def start_run(kind: str, student_id: uuid.UUID | None = None) -> uuid.UUID:
    with SessionLocal.begin() as session:
        run = RefreshRun(kind=kind, status="running", student_id=student_id)
        session.add(run)
        session.flush()
        return run.id


def finish_run(
    run_id: uuid.UUID, *, ok: bool, rows_changed: int | None = None, error: str | None = None
) -> None:
    with SessionLocal.begin() as session:
        session.execute(
            update(RefreshRun)
            .where(RefreshRun.id == run_id)
            .values(
                status="ok" if ok else "failed",
                finished_at=func.now(),
                rows_changed=rows_changed,
                error=error[:ERROR_MAX_LENGTH] if error else None,
            )
        )


def mark_interrupted_runs() -> int:
    """At startup nothing is running yet, so any 'running' row was cut off by a restart."""
    with SessionLocal.begin() as session:
        result = session.execute(
            update(RefreshRun)
            .where(RefreshRun.status == "running")
            .values(status="failed", finished_at=func.now(), error="interrupted: the server stopped")
        )
        return result.rowcount


def last_ok_finished(kind: str) -> datetime | None:
    with SessionLocal() as session:
        return session.scalar(
            select(func.max(RefreshRun.finished_at)).where(
                RefreshRun.kind == kind, RefreshRun.status == "ok"
            )
        )


def public_refresh_due(now: datetime | None = None) -> bool:
    """True when either public scraper has no good run within the max age."""
    now = now or datetime.now(UTC)
    max_age = timedelta(days=get_settings().public_refresh_max_age_days)
    for kind in PUBLIC_KINDS:
        finished = last_ok_finished(kind)
        if finished is None or now - finished > max_age:
            return True
    return False


def _default_steps() -> dict[str, Callable[[], int]]:
    # Imported here so the API starts even if a scraper module has a problem.
    from app.catalog.course_pages import refresh_course_info
    from app.catalog.degree_maps import refresh_degree_maps

    return {"degree_maps": refresh_degree_maps, "course_info": refresh_course_info}


def _run_public(run_ids: dict[str, uuid.UUID], steps: dict[str, Callable[[], int]]) -> None:
    try:
        for kind in PUBLIC_KINDS:
            try:
                rows_changed = steps[kind]()
            except Exception as error:  # a failed step must not stop the next one
                log.warning("public refresh %s failed: %s", kind, short_error(error))
                finish_run(run_ids[kind], ok=False, error=short_error(error))
            else:
                finish_run(run_ids[kind], ok=True, rows_changed=rows_changed)
    finally:
        _public_lock.release()


def start_public_refresh(
    steps: dict[str, Callable[[], int]] | None = None, *, wait: bool = False
) -> dict[str, uuid.UUID]:
    """Start both public scrapers in a background thread. Returns {kind: refresh_run id}."""
    if not _public_lock.acquire(blocking=False):
        raise RefreshAlreadyRunning
    try:
        run_ids = {kind: start_run(kind) for kind in PUBLIC_KINDS}
    except BaseException:
        _public_lock.release()
        raise
    thread = threading.Thread(
        target=_run_public,
        args=(run_ids, steps or _default_steps()),
        name="public-refresh",
        daemon=True,
    )
    thread.start()
    if wait:
        thread.join()
    return run_ids


def startup_refresh() -> None:
    """Called in a background thread at app startup. Never raises."""
    if not get_settings().public_refresh_on_startup:
        return
    try:
        mark_interrupted_runs()
        if public_refresh_due():
            run_ids = start_public_refresh()
            log.info("public refresh started on startup: %s", {k: str(v) for k, v in run_ids.items()})
    except RefreshAlreadyRunning:
        pass
    except Exception as error:
        log.warning("startup refresh skipped: %s", short_error(error))
