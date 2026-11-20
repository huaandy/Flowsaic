"""Prototype sign-in, /me endpoints, the session connect and the pages.
No database and no browser: the lookups and the connect are faked."""

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app import auth
from app import demo_seed
from app.demo_seed import ANDY, NEW_STUDENT_EMAIL, RETURNING_STUDENT_EMAIL
from app.main import app
from app.mysau import run as mysau_run
from app.routers import auth as auth_router
from app.routers import me as me_router

ANDY_ID = uuid.uuid4()
RETURNING_ID = uuid.uuid4()
NEW_ID = uuid.uuid4()
IDS = {ANDY.email: ANDY_ID, RETURNING_STUDENT_EMAIL: RETURNING_ID, NEW_STUDENT_EMAIL: NEW_ID}
NAMES = {ANDY_ID: "Andy Hua", RETURNING_ID: "Returning Student", NEW_ID: "New Student"}


def profile(student_id):
    return {
        "id": student_id, "name": NAMES[student_id],
        "email": "x@demo.flowsaic.test", "classification": None, "major": None, "catalog_year": None,
        "degree_plan": None, "has_hold": False, "total_hours_earned": None, "total_hours_needed": None,
        "audit_refreshed_at": None, "connected_mysau": False,
    }


@pytest.fixture
def cleared(monkeypatch):
    """Every clear_new_student call: what only_if was. Like the real one, it only empties
    user 5, and says whether it did."""
    calls = []

    def clear(only_if=None):
        calls.append(only_if)
        return only_if in (None, NEW_ID)

    monkeypatch.setattr(demo_seed, "clear_new_student", clear)
    return calls


@pytest.fixture
def client(monkeypatch, cleared):
    monkeypatch.setattr(auth, "find_student_id", lambda email: IDS.get(email))
    monkeypatch.setattr(auth_router, "load_profile", profile)
    monkeypatch.setattr(me_router, "load_profile", profile)
    monkeypatch.setattr(me_router, "load_completed_courses", lambda sid: [])
    monkeypatch.setattr(me_router, "load_audit", lambda sid: {"refreshed_at": None, "requirements": []})
    return TestClient(app)


@pytest.mark.parametrize("username, expected", [
    ("1", ANDY.email), (" 4 ", RETURNING_STUDENT_EMAIL), ("5", NEW_STUDENT_EMAIL), ("A@B.Test", "a@b.test"),
])
def test_usernames_1_to_5_are_shortcuts(username, expected):
    assert auth.login_email(username) == expected


def test_login_with_any_password_sets_a_session(client):
    response = client.post("/auth/login", json={"email": "1", "password": "anything at all"})
    assert response.status_code == 200 and response.json()["name"] == "Andy Hua"
    cookie = response.headers["set-cookie"]
    assert auth.SESSION_COOKIE in cookie and "HttpOnly" in cookie
    assert client.get("/me").json()["id"] == str(ANDY_ID)
    # An empty password works too, for now.
    assert client.post("/auth/login", json={"email": "4"}).json()["name"] == "Returning Student"
    assert client.get("/me").json()["id"] == str(RETURNING_ID)


def test_unknown_user_is_refused(client):
    response = client.post("/auth/login", json={"email": "6", "password": "x"})
    assert response.status_code == 401 and response.json() == {"error": "invalid_credentials"}
    assert client.post("/auth/login", json={"email": ""}).json() == {"error": "invalid_request"}


def test_me_needs_a_session(client):
    for path in ("/me", "/me/completed-courses", "/me/audit"):
        response = client.get(path)
        assert response.status_code == 401 and response.json() == {"error": "not_authenticated"}
    assert client.post("/me/connect-mysau", json={}).json() == {"error": "not_authenticated"}
    client.cookies.set(auth.SESSION_COOKIE, "made-up-token")
    assert client.get("/me").status_code == 401


def test_logout_ends_the_session(client):
    client.post("/auth/login", json={"email": "1"})
    assert client.get("/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/me").status_code == 401


def test_the_new_student_is_emptied_at_sign_in_and_sign_out(client, cleared):
    client.post("/auth/login", json={"email": "5"})
    assert cleared == [NEW_ID]  # signing in starts them empty
    client.post("/auth/logout")
    assert cleared == [NEW_ID, NEW_ID]  # and signing out leaves nothing behind
    client.post("/auth/login", json={"email": "5"})
    assert cleared == [NEW_ID, NEW_ID, NEW_ID]


def test_the_returning_student_keeps_their_data(client, cleared):
    client.post("/auth/login", json={"email": "4"})
    assert cleared == []  # not even asked at sign-in
    client.post("/auth/logout")
    assert cleared == [RETURNING_ID]  # sign-out asks with their id, and the clear refuses it
    assert demo_seed.clear_new_student(only_if=RETURNING_ID) is False


def test_logout_without_a_session_clears_nothing(client, cleared):
    assert client.post("/auth/logout").status_code == 204
    assert cleared == []


def test_the_new_student_is_emptied_at_startup(cleared, monkeypatch):
    from app import refresh

    monkeypatch.setattr(refresh, "startup_refresh", lambda: None)  # no real data refresh in a test
    with TestClient(app):  # runs the app's startup
        pass
    deadline = time.monotonic() + 5
    while None not in cleared and time.monotonic() < deadline:  # it runs in a thread
        time.sleep(0.01)
    assert None in cleared


def test_me_lists(client):
    client.post("/auth/login", json={"email": "1"})
    assert client.get("/me/completed-courses").json() == []
    assert client.get("/me/audit").json() == {"refreshed_at": None, "requirements": []}


def test_connect_uses_the_signed_in_student(client, monkeypatch):
    calls = []

    def start(student_id, fetch, **kwargs):
        calls.append((student_id, fetch))
        return {kind: uuid.uuid4() for kind in fetch}

    monkeypatch.setattr(mysau_run, "start_connect", start)
    client.post("/auth/login", json={"email": "5"})
    response = client.post("/me/connect-mysau")  # no body: both
    assert response.status_code == 202
    assert [run["kind"] for run in response.json()["runs"]] == ["sections", "audit"]
    assert calls == [(NEW_ID, ["sections", "audit"])]

    client.post("/me/connect-mysau", json={"fetch": ["audit", "audit"]})
    assert calls[-1] == (NEW_ID, ["audit"])
    assert client.post("/me/connect-mysau", json={"fetch": []}).json() == {"error": "invalid_request"}


def test_connect_already_running(client, monkeypatch):
    def busy(*args, **kwargs):
        raise mysau_run.ConnectAlreadyRunning

    monkeypatch.setattr(mysau_run, "start_connect", busy)
    client.post("/auth/login", json={"email": "4"})
    response = client.post("/me/connect-mysau")
    assert response.status_code == 409 and response.json() == {"error": "connect_already_running"}


def test_pages_are_served(client):
    login = client.get("/")
    assert login.status_code == 200 and 'id="username"' in login.text and 'type="password"' in login.text
    # After sign-in: the tabbed test page, with the student's profile as the first tab.
    assert 'location.href = "/dev"' in login.text
    page = client.get("/dev")
    assert page.status_code == 200
    for tab in ('data-tab="profile"', 'data-tab="advisor"', 'data-tab="lab"', 'data-tab="search"', 'data-tab="browse"', 'data-tab="database"'):
        assert tab in page.text
    assert "Connect mySAU" in page.text and "/auth/logout" in page.text
    old_home = client.get("/home", follow_redirects=False)
    assert old_home.status_code == 307 and old_home.headers["location"] == "/dev"
