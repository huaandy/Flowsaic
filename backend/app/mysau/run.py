"""Run a mySAU connect for one existing student: browser -> sections import -> audit save.

One connect at a time (one browser, one student signing in). Each requested kind
('sections', 'audit') gets its own refresh_runs row with the student's id.
Errors stored in refresh_runs are our own short codes and the error type only.
"""

import threading
import uuid
from collections.abc import Callable

from app.mysau.audit_store import StudentNotFound, save_audit, student_exists
from app.mysau.connect import Captured, ConnectError, run_browser
from app.mysau.sections_import import ExportNotUnderstood, import_export_bytes
from app.refresh import finish_run, start_run

KINDS = ("sections", "audit")
_lock = threading.Lock()


class ConnectAlreadyRunning(RuntimeError):
    pass


def _safe_error(step: str, error: BaseException) -> str:
    if isinstance(error, ExportNotUnderstood):
        return f"{step}: {error}"  # our own message, about the file's columns
    return f"{step} failed ({type(error).__name__})"


def run_connect(
    student_id: uuid.UUID,
    fetch: list[str],
    run_ids: dict[str, uuid.UUID],
    *,
    browser: Callable[[set[str], Callable[[str], None]], Captured] = run_browser,
    status: Callable[[str], None] = lambda _: None,
) -> None:
    try:
        captured = browser(set(fetch), status)
    except ConnectError as error:
        for run_id in run_ids.values():
            finish_run(run_id, ok=False, error=str(error))
        return
    except Exception as error:
        for run_id in run_ids.values():
            finish_run(run_id, ok=False, error=_safe_error("browser", error))
        return

    try:
        if "sections" in run_ids:
            try:
                if captured.sections_csv is None:
                    raise ConnectError("sections_not_received")
                result = import_export_bytes(captured.sections_csv)
                status(f"imported {len(result.parsed.sections)} sections")
                finish_run(run_ids["sections"], ok=True, rows_changed=len(result.parsed.sections))
            except ConnectError as error:
                finish_run(run_ids["sections"], ok=False, error=str(error))
            except Exception as error:
                finish_run(run_ids["sections"], ok=False, error=_safe_error("sections_import", error))

        if "audit" in run_ids:
            try:
                if captured.audit_pdf is None:
                    raise ConnectError("audit_not_received")
                from app.mysau.audit_parser import parse_audit_pdf

                parsed = parse_audit_pdf(captured.audit_pdf)
                rows = save_audit(student_id, parsed)
                status(f"saved the audit: {len(parsed.requirements)} requirements, {len(parsed.courses)} courses")
                finish_run(run_ids["audit"], ok=True, rows_changed=rows)
            except ConnectError as error:
                finish_run(run_ids["audit"], ok=False, error=str(error))
            except Exception as error:
                finish_run(run_ids["audit"], ok=False, error=_safe_error("audit_save", error))
    finally:
        captured.audit_pdf = None  # drop the PDF bytes as soon as we are done
        captured.sections_csv = None


def start_connect(
    student_id: uuid.UUID, fetch: list[str], *, wait: bool = False, **kwargs
) -> dict[str, uuid.UUID]:
    """Check the student, then run the connect in a background thread (or wait for it)."""
    if not student_exists(student_id):
        raise StudentNotFound
    if not _lock.acquire(blocking=False):
        raise ConnectAlreadyRunning
    try:
        kinds = [kind for kind in KINDS if kind in fetch]
        run_ids = {kind: start_run(kind, student_id) for kind in kinds}
    except BaseException:
        _lock.release()
        raise

    def target() -> None:
        try:
            run_connect(student_id, kinds, run_ids, **kwargs)
        finally:
            _lock.release()

    thread = threading.Thread(target=target, name="mysau-connect", daemon=True)
    thread.start()
    if wait:
        thread.join()
    return run_ids
