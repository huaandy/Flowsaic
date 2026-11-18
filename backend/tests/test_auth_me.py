"""Prototype sign-in, /me endpoints, the session connect and the pages.
No database and no browser: the lookups and the connect are faked."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.demo_seed import ALEX, NEW_STUDENT_EMAIL
from app.main import app
from app.mysau import run as mysau_run
from app.routers import auth as auth_router
from app.routers import me as me_router

ALEX_ID = uuid.uuid4()
NEW_ID = uuid.uuid4()
IDS = {ALEX.email: ALEX_ID, NEW_STUDENT_EMAIL: NEW_ID}


def profile(student_id):
    return {
        "id": student_id, "name": "Alex Rivera" if student_id == ALEX_ID else "New Student",
        "email": "x@demo.flowsaic.test", "classification": None, "major": None, "catalog_year": None,
        "degree_plan": None, "has_hold": False, "total_hours_earned": None, "total_hours_needed": None,
        "audit_refreshed_at": None, "connected_mysau": False,
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth, "find_student_id", lambda email: IDS.get(email))
    monkeypatch.setattr(auth_router, "load_profile", profile)
    monkeypatch.setattr(me_router, "load_profile", profile)
    monkeypatch.setattr(me_router, "load_completed_courses", lambda sid: [])
    monkeypatch.setattr(me_router, "load_audit", lambda sid: {"refreshed_at": None, "requirements": []})
    return TestClient(app)


@pytest.mark.parametrize("username, expected", [("1", ALEX.email), (" 4 ", NEW_STUDENT_EMAIL), ("A@B.Test", "a@b.test")])
def test_usernames_1_to_4_are_shortcuts(username, expected):
    assert auth.login_email(username) == expected


def test_login_with_any_password_sets_a_session(client):
    response = client.post("/auth/login", json={"email": "1", "password": "anything at all"})
    assert response.status_code == 200 and response.json()["name"] == "Alex Rivera"
    cookie = response.headers["set-cookie"]
    assert auth.SESSION_COOKIE in cookie and "HttpOnly" in cookie
    assert client.get("/me").json()["id"] == str(ALEX_ID)
    # An empty password works too, for now.
    assert client.post("/auth/login", json={"email": "4"}).json()["name"] == "New Student"
    assert client.get("/me").json()["id"] == str(NEW_ID)


def test_unknown_user_is_refused(client):
    response = client.post("/auth/login", json={"email": "5", "password": "x"})
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
    client.post("/auth/login", json={"email": "4"})
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
