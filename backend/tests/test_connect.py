"""mySAU connect: login detection, file capture rules, the run, and the endpoint.
No browser, no network and no database: all faked."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mysau import audit_parser, connect, run
from app.mysau.audit_store import StudentNotFound
from app.mysau.connect import Captured, ConnectError, is_wanted, wait_for_login

client = TestClient(app)


# --- login --------------------------------------------------------------------------------

class FakeLogin:
    def __init__(self, page):
        self.page = page
        self.first = self

    def count(self):
        return 0 if self.page.signed_in else 1

    def is_visible(self):
        return not self.page.signed_in

    def click(self):
        self.page.clicks += 1
        self.page.url = self.page.after_click


class FakePage:
    """url changes as time passes, like a student signing in at Microsoft."""

    def __init__(self, signed_in=False, after_click="https://my.saumag.edu/ICS/", signs_in_after=0):
        self.signed_in = signed_in
        self.url = "https://my.saumag.edu/ICS/"
        self.after_click = after_click
        self.signs_in_after = signs_in_after
        self.clicks = 0
        self.waits = 0

    def get_by_role(self, role, name, exact=False):
        assert (role, name) == ("button", "Login")
        return FakeLogin(self)

    def wait_for_load_state(self, *args, **kwargs):
        pass

    def wait_for_timeout(self, ms):
        self.waits += 1
        if self.waits >= self.signs_in_after:
            self.url, self.signed_in = "https://my.saumag.edu/ICS/", True


def test_already_signed_in():
    page = FakePage(signed_in=True)
    wait_for_login(page, timeout_seconds=1)
    assert page.clicks == 0


def test_login_signs_in_at_once():
    page = FakePage(signs_in_after=1)
    wait_for_login(page, timeout_seconds=5)
    assert page.clicks == 1


def test_login_through_microsoft_waits_for_the_student():
    page = FakePage(after_click="https://login.microsoftonline.com/x", signs_in_after=3)
    wait_for_login(page, timeout_seconds=10)
    assert page.signed_in and page.waits >= 3


def test_login_timeout(monkeypatch):
    page = FakePage(after_click="https://login.microsoftonline.com/x", signs_in_after=10**9)
    with pytest.raises(ConnectError, match="login_timeout"):
        wait_for_login(page, timeout_seconds=0)


# --- capture ------------------------------------------------------------------------------

def test_is_wanted():
    assert is_wanted("pdf", {"content-type": "application/pdf"})
    assert is_wanted("pdf", {"content-type": "application/octet-stream", "content-disposition": 'attachment; filename="a.pdf"'})
    assert not is_wanted("pdf", {"content-type": "text/html"})
    assert is_wanted("csv", {"content-type": "text/csv; charset=utf-8"})
    assert is_wanted("csv", {"content-disposition": "attachment; filename=CourseSchedule.csv"})
    assert not is_wanted("csv", {"content-type": "application/pdf"})


# --- run ----------------------------------------------------------------------------------

@pytest.fixture
def finished(monkeypatch):
    runs = {}
    monkeypatch.setattr(run, "finish_run", lambda run_id, **kw: runs.__setitem__(run_id, kw))
    return runs


def ids():
    return {"sections": uuid.uuid4(), "audit": uuid.uuid4()}


def test_run_imports_sections_and_saves_the_audit(monkeypatch, finished):
    student = uuid.uuid4()
    saved = {}
    monkeypatch.setattr(run, "import_export_bytes",
                        lambda data: SimpleNamespace(parsed=SimpleNamespace(sections=[1, 2, 3])))
    monkeypatch.setattr(audit_parser, "parse_audit_pdf",
                        lambda data: SimpleNamespace(requirements=[1], courses=[1, 2]))
    monkeypatch.setattr(run, "save_audit", lambda sid, parsed: saved.setdefault(sid, 3))
    captured = Captured(sections_csv=b"csv", audit_pdf=b"%PDF")
    run_ids = ids()
    run.run_connect(student, ["sections", "audit"], run_ids, browser=lambda fetch, status: captured)
    assert finished[run_ids["sections"]] == {"ok": True, "rows_changed": 3}
    assert finished[run_ids["audit"]] == {"ok": True, "rows_changed": 3}
    assert saved == {student: 3}
    assert captured.audit_pdf is None  # bytes dropped after use


def test_sections_only_connect_needs_no_student(monkeypatch, finished):
    # A teammate loading the live course schedule onto their own laptop: no Flowsaic student.
    started = []
    monkeypatch.setattr(run, "start_run", lambda kind, student_id=None: started.append((kind, student_id)) or uuid.uuid4())
    monkeypatch.setattr(run, "student_exists", lambda sid: pytest.fail("no student lookup without a student"))
    monkeypatch.setattr(run, "import_export_bytes",
                        lambda data: SimpleNamespace(parsed=SimpleNamespace(sections=[1, 2])))
    fetched = []

    def browser(fetch, status):
        fetched.append(set(fetch))
        return Captured(sections_csv=b"csv")

    run_ids = run.start_connect(None, ["sections"], wait=True, browser=browser)
    assert started == [("sections", None)] and fetched == [{"sections"}]
    assert finished[run_ids["sections"]] == {"ok": True, "rows_changed": 2}


def test_the_audit_always_needs_a_student():
    with pytest.raises(run.AuditNeedsStudent):
        run.start_connect(None, ["sections", "audit"])


def test_a_failed_login_fails_every_run(finished):
    def browser(fetch, status):
        raise ConnectError("login_timeout")

    run_ids = ids()
    run.run_connect(uuid.uuid4(), ["sections", "audit"], run_ids, browser=browser)
    assert {r["error"] for r in finished.values()} == {"login_timeout failed"}
    assert all(r["ok"] is False for r in finished.values())


def test_errors_never_carry_page_content(monkeypatch, finished):
    def boom(data):
        raise ValueError("<html>Name: Private Person, ID 123</html>")

    monkeypatch.setattr(audit_parser, "parse_audit_pdf", boom)
    run_ids = {"audit": uuid.uuid4()}
    run.run_connect(uuid.uuid4(), ["audit"], run_ids, browser=lambda f, s: Captured(audit_pdf=b"%PDF"))
    assert finished[run_ids["audit"]]["error"] == "audit_save failed (ValueError)"


def test_a_missing_file_is_reported(finished):
    run_ids = {"sections": uuid.uuid4()}
    run.run_connect(uuid.uuid4(), ["sections"], run_ids, browser=lambda f, s: Captured())
    assert finished[run_ids["sections"]] == {"ok": False, "error": "sections_not_received failed"}


def test_browser_steps_wrap_unknown_errors():
    error = ConnectError("audit_export", TimeoutError("waiting for https://my.saumag.edu/?token=abc"))
    assert str(error) == "audit_export failed (TimeoutError)"


# --- endpoint -----------------------------------------------------------------------------

def test_connect_endpoint(monkeypatch):
    student = uuid.uuid4()
    run_ids = ids()
    calls = []

    def start(student_id, fetch, **kwargs):
        calls.append((student_id, fetch))
        return run_ids

    monkeypatch.setattr(run, "start_connect", start)
    response = client.post("/connect/mysau", json={"student_id": str(student), "fetch": ["audit", "sections", "audit"]})
    assert response.status_code == 202
    assert calls == [(student, ["audit", "sections"])]
    assert {r["kind"] for r in response.json()["runs"]} == {"sections", "audit"}


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(StudentNotFound(), 404, "student_not_found"), (run.ConnectAlreadyRunning(), 409, "connect_already_running")],
)
def test_connect_endpoint_errors(monkeypatch, error, status, code):
    def start(*args, **kwargs):
        raise error

    monkeypatch.setattr(run, "start_connect", start)
    response = client.post("/connect/mysau", json={"student_id": str(uuid.uuid4())})
    assert (response.status_code, response.json()) == (status, {"error": code})


def test_connect_endpoint_validates_input():
    assert client.post("/connect/mysau", json={"student_id": "x"}).json() == {"error": "invalid_request"}
    bad = client.post("/connect/mysau", json={"student_id": str(uuid.uuid4()), "fetch": ["grades"]})
    assert bad.status_code == 422
    empty = client.post("/connect/mysau", json={"student_id": str(uuid.uuid4()), "fetch": []})
    assert empty.status_code == 422


def test_connect_module_never_saves_session_state():
    source = open(connect.__file__, encoding="utf-8").read()
    for forbidden in ("storage_state(", "tracing.start", "record_video", "screenshot(", "launch_persistent_context", ".save_as("):
        assert forbidden not in source
