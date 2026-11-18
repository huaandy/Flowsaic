"""mySAU connect: open a real (headed) browser, let the student sign in, then export the
course schedule and the degree audit. Selectors come from a codegen recording (Nov 17).

Privacy (prompt 2), enforced here:
- A fresh browser context every run with no storage_state, no persistent profile, and
  downloads refused; the context and browser are closed in `finally`.
- No tracing, video or screenshots.
- The sign-in (Microsoft + Duo) is done by the student. Nothing here types into it.
- Files are captured from the network response body, in memory. The browser is shown a
  small "received" page instead, so the CSV and the audit PDF never touch the disk.
- Errors carry our own step name and the error type only, never page content or URLs.

The browser opens on the machine running the backend. Fine for the demo laptop; a hosting
problem for semester 2 (noted in AGENTS.md).
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

MYSAU_URL = "https://my.saumag.edu/ICS/"
MYSAU_HOST = "my.saumag.edu"
LOGIN_TIMEOUT_SECONDS = 300  # the student has 5 minutes to sign in
STEP_TIMEOUT_MS = 60_000
RECALCULATE_TIMEOUT_MS = 120_000
CAPTURE_TIMEOUT_SECONDS = 90
RECEIVED_PAGE = (
    "<!doctype html><title>Flowsaic</title><body style='font-family:sans-serif;padding:2em'>"
    "<p>Flowsaic received this file. You can close this tab.</p></body>"
)


class ConnectError(RuntimeError):
    """A step failed. The message is ours: a step name and the error type, nothing else."""

    def __init__(self, step: str, cause: BaseException | None = None) -> None:
        self.step = step
        super().__init__(f"{step} failed" + (f" ({type(cause).__name__})" if cause else ""))


@dataclass
class Captured:
    sections_csv: bytes | None = None
    audit_pdf: bytes | None = None


def is_wanted(kind: str, headers: dict[str, str]) -> bool:
    """Is this response the file we are waiting for? kind is 'csv' or 'pdf'."""
    content_type = headers.get("content-type", "").lower()
    disposition = headers.get("content-disposition", "").lower()
    if kind == "pdf":
        return "application/pdf" in content_type or ".pdf" in disposition
    return "text/csv" in content_type or ".csv" in disposition or (
        "attachment" in disposition and "excel" in content_type
    )


def capture_file(context, page, kind: str, click: Callable[[], None]) -> bytes:
    """Run `click` and return the body of the file response it triggers (in memory)."""
    captured: dict[str, bytes] = {}

    def handle(route) -> None:
        if route.request.resource_type not in ("document", "xhr", "fetch", "other") or captured:
            route.continue_()
            return
        response = route.fetch()
        if is_wanted(kind, {k.lower(): v for k, v in response.headers.items()}):
            captured["body"] = response.body()
            route.fulfill(status=200, content_type="text/html", body=RECEIVED_PAGE)
        else:
            route.fulfill(response=response)

    context.route("**/*", handle)
    try:
        click()
        deadline = time.monotonic() + CAPTURE_TIMEOUT_SECONDS
        while "body" not in captured and time.monotonic() < deadline:
            page.wait_for_timeout(500)
    finally:
        context.unroute("**/*", handle)
    if "body" not in captured:
        raise ConnectError(f"{kind}_not_received")
    return captured["body"]


def _on_mysau(page) -> bool:
    return urlparse(page.url).hostname == MYSAU_HOST


def wait_for_login(page, timeout_seconds: int = LOGIN_TIMEOUT_SECONDS) -> None:
    """Handles: already signed in; Login signs in at once; Login goes to Microsoft + Duo.

    Signed in = back on my.saumag.edu with the Login button gone (it becomes a profile tab).
    """
    login = page.get_by_role("button", name="Login", exact=True)
    if login.count() and login.first.is_visible():
        login.first.click()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if _on_mysau(page):
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
                if login.count() == 0:
                    return
        except Exception:
            pass  # the page is navigating (to or from Microsoft); look again in a second
        page.wait_for_timeout(1_000)
    raise ConnectError("login_timeout")


def export_sections(context, page) -> bytes:
    page.get_by_role("link", name="Course Schedule").click()
    page.wait_for_load_state("domcontentloaded")
    data = capture_file(context, page, "csv", lambda: page.get_by_role("link", name="CSV").click())
    for other in context.pages:  # the export opens a popup tab
        if other is not page:
            other.close()
    return data


def export_audit(context, page) -> bytes:
    page.get_by_role("link", name="Student", exact=True).click()
    page.get_by_role("link", name="Academics").click()
    page.get_by_role("link", name="View All Details").click()
    page.get_by_role("button", name="Recalculate Student Progress").click()
    try:  # recalculation reloads the page; wait for it to settle
        page.wait_for_load_state("networkidle", timeout=RECALCULATE_TIMEOUT_MS)
    except Exception:
        pass
    printable = page.get_by_role("link", name=re.compile(r"^Printable Degree Audit"))
    printable.wait_for(timeout=RECALCULATE_TIMEOUT_MS)
    data = capture_file(context, page, "pdf", lambda: printable.click())
    for other in context.pages:
        if other is not page:
            other.close()
    return data


def run_browser(fetch: set[str], status: Callable[[str], None] = lambda _: None) -> Captured:
    """Open the browser, wait for the student's sign-in, export what was asked for."""
    from playwright.sync_api import sync_playwright

    result = Captured()
    step = "open_browser"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = None
        try:
            # Fresh context: no storage_state, no tracing, no video, downloads refused.
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            step = "open_mysau"
            page.goto(MYSAU_URL)
            step = "login"
            status("waiting for the student to sign in")
            wait_for_login(page)
            if "sections" in fetch:
                step = "sections_export"
                status("exporting the course schedule")
                result.sections_csv = export_sections(context, page)
            if "audit" in fetch:
                step = "audit_export"
                status("recalculating and downloading the degree audit")
                result.audit_pdf = export_audit(context, page)
        except ConnectError:
            raise
        except Exception as error:
            raise ConnectError(step, error) from None
        finally:
            if context is not None:
                context.close()
            browser.close()
    return result
