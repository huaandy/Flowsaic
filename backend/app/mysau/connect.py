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
from dataclasses import dataclass, field
from urllib.parse import urlparse

MYSAU_URL = "https://my.saumag.edu/ICS/"
MYSAU_HOST = "my.saumag.edu"
LOGIN_TIMEOUT_SECONDS = 300  # the student has 5 minutes to sign in
SIGNED_IN_CHECKS = 3  # signed in = the same signed-in mySAU page for this many 1 s checks
HOME_ATTEMPTS = 3
STEP_TIMEOUT_MS = 60_000
RECALCULATE_TIMEOUT_MS = 120_000
CAPTURE_TIMEOUT_SECONDS = 90
RECEIVED_PAGE = (
    "<!doctype html><title>Flowsaic</title><body style='font-family:sans-serif;padding:2em'>"
    "<p>Flowsaic received this file. You can close this tab.</p></body>"
)


# Playwright error messages quote the page (element HTML, URLs), so they are never stored.
# Only these fixed hints are, picked by matching the message here in memory.
_ERROR_HINTS = (
    ("strict mode violation", "more_than_one_match"),
    ("has been closed", "page_closed"),
    ("execution context was destroyed", "page_navigated"),
    ("element is not attached", "page_navigated"),
    ("element is not visible", "not_visible"),
    ("interrupted by another navigation", "navigation_interrupted"),
    ("frame was detached", "page_navigated"),
    ("download is starting", "download"),
    ("page crashed", "page_crashed"),
    ("net::", "network"),
)


def error_hint(error: BaseException) -> str | None:
    message = str(error).lower()
    return next((hint for needle, hint in _ERROR_HINTS if needle in message), None)


# Where page content can start in a Playwright message: a quote, a tag, a bracket, a URL.
_PAGE_CONTENT_STARTS = re.compile(r"""["'`<(\[{]|https?:|www\.""", re.IGNORECASE)
SUMMARY_MAX = 80


def playwright_summary(error: BaseException) -> str | None:
    """For a Playwright error no hint matches: the start of Playwright's own wording only.

    The first line is cut before anything that can quote the page (selector text, element
    HTML, URLs), and only letters, digits and plain punctuation are kept, e.g.
    "Locator.click: Element is outside of the viewport". Never for our own or other errors.
    """
    if not type(error).__module__.startswith("playwright"):
        return None
    first_line = str(error).splitlines()[0] if str(error) else ""
    text = _PAGE_CONTENT_STARTS.split(first_line, maxsplit=1)[0]
    text = re.sub(r"[^A-Za-z0-9 .:_-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" :.-")
    return text[:SUMMARY_MAX].rstrip() or None


class ConnectError(RuntimeError):
    """A step failed. The message is ours: a step name, the error type and a fixed hint.

    When no hint fits a Playwright error, the start of Playwright's own wording is kept
    instead (see playwright_summary), so a new kind of failure still says what happened.
    """

    def __init__(self, step: str, cause: BaseException | None = None) -> None:
        self.step = step
        detail = ""
        if cause is not None:
            hint = error_hint(cause) or playwright_summary(cause)
            detail = f" ({type(cause).__name__}{': ' + hint if hint else ''})"
        super().__init__(f"{step} failed{detail}")


@dataclass
class Captured:
    sections_csv: bytes | None = None
    audit_pdf: bytes | None = None
    errors: dict[str, str] = field(default_factory=dict)  # kind -> our error message


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

    Signed in = back on my.saumag.edu, fully loaded, with the Login button gone (it becomes a
    profile tab), on the same page for SIGNED_IN_CHECKS checks in a row. Coming back from
    Microsoft, mySAU redirects a few more times; a page caught mid-redirect has no Login
    button yet either, and navigating away from it then gets interrupted.
    """
    login = page.get_by_role("button", name="Login", exact=True)
    if login.count() and login.first.is_visible():
        login.first.click()
    deadline = time.monotonic() + timeout_seconds
    steady, last_url = 0, None
    while time.monotonic() < deadline:
        try:
            if _on_mysau(page):
                page.wait_for_load_state("load", timeout=5_000)
                if login.count() == 0:
                    steady = steady + 1 if page.url == last_url else 1
                    last_url = page.url
                    if steady >= SIGNED_IN_CHECKS:
                        return
                else:
                    steady = 0
            else:
                steady = 0
        except Exception:
            steady = 0  # the page is navigating (to or from Microsoft); look again in a second
        page.wait_for_timeout(1_000)
    raise ConnectError("login_timeout")


Mark = Callable[[str], None]


def close_other_pages(context, page) -> None:
    """The exports open popup tabs; close them so the next step only sees the main page."""
    for other in list(context.pages):
        if other is not page:
            try:
                other.close()
            except Exception:
                pass


def go_home(page, attempts: int = HOME_ATTEMPTS) -> None:
    """Every export starts from the mySAU home page, where its selectors were recorded.

    A navigation mySAU starts by itself (a redirect after sign-in) interrupts ours, so wait
    for the page to settle and try again. If mySAU keeps redirecting us to another of its
    own pages, that page has the same top menu, so go on from there.
    """
    for attempt in range(1, attempts + 1):
        try:
            page.goto(MYSAU_URL)
            page.wait_for_load_state("load")
            return
        except Exception as error:
            if attempt == attempts:
                if error_hint(error) == "navigation_interrupted" and _on_mysau(page):
                    page.wait_for_load_state("load")
                    return
                raise
            page.wait_for_timeout(2_000)
            try:
                page.wait_for_load_state("load", timeout=10_000)
            except Exception:
                pass


def export_sections(context, page, mark: Mark = lambda _: None) -> bytes:
    try:
        mark("home")
        go_home(page)
        mark("course_schedule_link")
        page.get_by_role("link", name="Course Schedule").click()
        page.wait_for_load_state("domcontentloaded")
        mark("csv_capture")
        return capture_file(context, page, "csv", lambda: page.get_by_role("link", name="CSV").click())
    finally:
        close_other_pages(context, page)


def settle(page) -> None:
    """Wait for the page a click opened to finish loading (no-op if nothing navigated)."""
    try:
        page.wait_for_load_state("load")
    except Exception:
        pass


def click_nav(page, name: str, *, exact: bool = False, role: str = "link") -> None:
    """Click a menu link and wait for its page.

    mySAU pages carry the same menu more than once (a desktop menu and a hidden mobile one,
    or the same link in two places), so click the first visible match. A click on a page
    that is still loading can fail on its own; let it settle and try once more.
    """
    link = page.get_by_role(role, name=name, exact=exact).filter(visible=True).first
    settle(page)
    try:
        link.click()
    except Exception as error:
        if type(error).__name__ == "TimeoutError":
            raise
        page.wait_for_timeout(2_000)
        settle(page)
        link.click()
    settle(page)


def export_audit(context, page, mark: Mark = lambda _: None) -> bytes:
    try:
        mark("home")
        go_home(page)
        mark("student_link")
        click_nav(page, "Student", exact=True)
        mark("academics_link")
        click_nav(page, "Academics")
        mark("view_all_details_link")
        click_nav(page, "View All Details")
        mark("recalculate_button")
        page.get_by_role("button", name="Recalculate Student Progress").click()
        try:  # recalculation reloads the page; wait for it to settle
            page.wait_for_load_state("networkidle", timeout=RECALCULATE_TIMEOUT_MS)
        except Exception:
            pass
        mark("printable_link")
        printable = page.get_by_role("link", name=re.compile(r"^Printable Degree Audit"))
        printable.wait_for(timeout=RECALCULATE_TIMEOUT_MS)
        mark("pdf_capture")
        return capture_file(context, page, "pdf", lambda: printable.click())
    finally:
        close_other_pages(context, page)


# kind -> (step name, status line, export function, Captured field)
EXPORTS = {
    "sections": ("sections_export", "exporting the course schedule", export_sections, "sections_csv"),
    "audit": ("audit_export", "recalculating and downloading the degree audit", export_audit, "audit_pdf"),
}


def run_exports(context, page, fetch: set[str], status: Callable[[str], None], result: Captured,
                exports: dict = EXPORTS) -> None:
    """Run each requested export on its own: one that fails doesn't lose the others.

    A failure is stored in result.errors[kind] as e.g.
    "audit_export:academics_link failed (Error: more_than_one_match)".
    """
    for kind, (step, line, export, attr) in exports.items():
        if kind not in fetch:
            continue
        status(line)
        where = {"sub": "start"}

        def mark(sub: str, where=where) -> None:
            where["sub"] = sub

        try:
            setattr(result, attr, export(context, page, mark))
        except ConnectError as error:  # one of ours, e.g. pdf_not_received
            result.errors[kind] = f"{step}:{where['sub']} failed ({error.step})"
        except Exception as error:
            result.errors[kind] = str(ConnectError(f"{step}:{where['sub']}", error))


def run_browser(fetch: set[str], status: Callable[[str], None] = lambda _: None) -> Captured:
    """Open the browser, wait for the student's sign-in, export what was asked for.

    A failure before the exports (browser, sign-in) raises ConnectError and fails every run.
    A failed export is recorded in result.errors under its kind; the others still run.
    """
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
            step = "export"
            run_exports(context, page, fetch, status, result)
        except ConnectError:
            raise
        except Exception as error:
            raise ConnectError(step, error) from None
        finally:
            if context is not None:
                context.close()
            browser.close()
    return result
