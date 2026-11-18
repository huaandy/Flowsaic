"""/me/events, /me/preferences and /me/settings, plus user 5's reset. Storage is an in-memory
fake keyed by student, so "another student's row" is tested the same way the SQL scopes it."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import demo_seed
from app.auth import ApiError
from app.models import Base, StudentPreferences, StudentSettings
from app.routers import planning

ALEX, JORDAN = uuid.uuid4(), uuid.uuid4()
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=="


class FakeStore:
    def __init__(self):
        self.events: dict[uuid.UUID, dict] = {}  # id -> row with student_id
        self.preferences: dict[uuid.UUID, dict] = {}
        self.settings: dict[uuid.UUID, dict] = {}

    def install(self, monkeypatch):
        monkeypatch.setattr(planning, "list_events", self.list_events)
        monkeypatch.setattr(planning, "create_event", self.create_event)
        monkeypatch.setattr(planning, "update_event", self.update_event)
        monkeypatch.setattr(planning, "delete_event", self.delete_event)
        monkeypatch.setattr(planning, "load_preferences", lambda sid: dict(self.preferences.get(sid, planning.DEFAULT_PREFERENCES)))
        monkeypatch.setattr(planning, "store_preferences", self.store("preferences"))
        monkeypatch.setattr(planning, "load_settings", lambda sid: dict(self.settings.get(sid, planning.DEFAULT_SETTINGS)))
        monkeypatch.setattr(planning, "store_settings", self.store("settings"))

    def _out(self, row):
        return {k: v for k, v in row.items() if k != "student_id"}

    def list_events(self, sid):
        return [self._out(r) for r in self.events.values() if r["student_id"] == sid]

    def create_event(self, sid, body):
        if sum(r["student_id"] == sid for r in self.events.values()) >= planning.MAX_EVENTS:
            raise ApiError(422, "too_many_events")
        row = {"id": uuid.uuid4(), "student_id": sid, **body.model_dump(), "created_at": NOW, "updated_at": NOW}
        self.events[row["id"]] = row
        return self._out(row)

    def update_event(self, sid, event_id, body):
        row = self.events.get(event_id)
        if row is None or row["student_id"] != sid:
            raise ApiError(404, "event_not_found")
        row.update(body.model_dump())
        return self._out(row)

    def delete_event(self, sid, event_id):
        row = self.events.get(event_id)
        if row is None or row["student_id"] != sid:
            raise ApiError(404, "event_not_found")
        del self.events[event_id]

    def store(self, kind):
        def save(sid, values):
            getattr(self, kind)[sid] = {**values, "updated_at": NOW}
            return getattr(self, kind)[sid]
        return save


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore()
    fake.install(monkeypatch)
    return fake


def signed_in(monkeypatch, student_id):
    from app import auth
    from app.main import app
    from app.routers import auth as auth_router

    monkeypatch.setattr(auth, "find_student_id", lambda email: student_id)
    monkeypatch.setattr(auth_router, "load_profile", lambda sid: {
        "id": sid, "name": "Student", "email": "s@demo.flowsaic.test", "classification": None, "major": None,
        "catalog_year": None, "degree_plan": None, "has_hold": False, "total_hours_earned": None,
        "total_hours_needed": None, "audit_refreshed_at": None, "connected_mysau": False})
    client = TestClient(app)
    client.post("/auth/login", json={"email": "1"})
    return client


@pytest.fixture
def alex(monkeypatch, store):
    return signed_in(monkeypatch, ALEX)


WORK = {"title": " Work shift ", "day": "T", "start_time": "15:00", "end_time": "18:00", "location": "Student Services",
        "category": "work", "recurrence": "weekly", "priority": "high", "fixed": True}


# --- events -------------------------------------------------------------------------------------------

def test_planning_endpoints_need_a_session():
    from app.main import app

    client = TestClient(app)
    for method, path in (("get", "/me/events"), ("post", "/me/events"), ("put", f"/me/events/{uuid.uuid4()}"),
                         ("delete", f"/me/events/{uuid.uuid4()}"), ("get", "/me/preferences"),
                         ("put", "/me/preferences"), ("get", "/me/settings"), ("put", "/me/settings")):
        response = getattr(client, method)(path, **({"json": WORK} if method in ("post", "put") else {}))
        assert response.status_code == 401 and response.json() == {"error": "not_authenticated"}, path


def test_event_crud(alex):
    assert alex.get("/me/events").json() == []
    response = alex.post("/me/events", json=WORK)
    assert response.status_code == 201
    event = response.json()
    assert event["title"] == "Work shift" and event["day"] == "T" and event["fixed"] is True
    assert event["start_time"] == "15:00" and event["category"] == "work"
    changed = alex.put(f"/me/events/{event['id']}", json={**WORK, "end_time": "17:00", "fixed": False}).json()
    assert changed["end_time"] == "17:00" and changed["fixed"] is False
    assert [e["id"] for e in alex.get("/me/events").json()] == [event["id"]]
    assert alex.delete(f"/me/events/{event['id']}").status_code == 204
    assert alex.get("/me/events").json() == []


def test_event_defaults(alex):
    event = alex.post("/me/events", json={"title": "Study", "day": "R", "start_time": "08:00", "end_time": "09:00"}).json()
    assert (event["category"], event["recurrence"], event["priority"], event["fixed"], event["location"]) == \
        ("personal_study", "weekly", "normal", False, None)


@pytest.mark.parametrize("change", [
    {"day": "S"}, {"day": "Mon"}, {"start_time": "9:00"}, {"start_time": "25:00"}, {"end_time": "14:00"},
    {"end_time": "15:00"}, {"title": ""}, {"title": "   "}, {"title": "x" * 81}, {"category": "academic"},
    {"recurrence": "daily"}, {"priority": "urgent"}, {"location": "x" * 121},
])
def test_event_validation(alex, change):
    response = alex.post("/me/events", json={**WORK, **change})
    assert response.status_code == 422 and response.json() == {"error": "invalid_request"}


def test_another_students_event_is_not_found(monkeypatch, store):
    alex = signed_in(monkeypatch, ALEX)
    event_id = alex.post("/me/events", json=WORK).json()["id"]
    jordan = signed_in(monkeypatch, JORDAN)
    assert jordan.get("/me/events").json() == []
    for response in (jordan.put(f"/me/events/{event_id}", json=WORK), jordan.delete(f"/me/events/{event_id}")):
        assert response.status_code == 404 and response.json() == {"error": "event_not_found"}
    assert len(store.events) == 1


def test_too_many_events(alex, monkeypatch):
    monkeypatch.setattr(planning, "MAX_EVENTS", 1)
    alex.post("/me/events", json=WORK)
    response = alex.post("/me/events", json=WORK)
    assert response.status_code == 422 and response.json() == {"error": "too_many_events"}


def test_events_sort_by_day_then_time():
    rows = [{"day": d, "start_time": t, "title": "x"} for d, t in (("F", "08:00"), ("M", "13:00"), ("R", "09:00"), ("M", "08:00"))]
    assert sorted(rows, key=lambda e: (planning.DAY_ORDER.index(e["day"]), e["start_time"], e["title"]))[0] == \
        {"day": "M", "start_time": "08:00", "title": "x"}


# --- preferences ----------------------------------------------------------------------------------------

def test_preferences_default_when_never_saved(alex):
    body = alex.get("/me/preferences").json()
    assert body == {**planning.DEFAULT_PREFERENCES, "updated_at": None}


def test_preferences_change_only_what_is_sent(alex):
    body = alex.put("/me/preferences", json={"preferred_time": "midday", "preferred_days": "rtm",
                                             "delivery": ["online", "in_person"]}).json()
    assert body["preferred_time"] == "midday" and body["preferred_days"] == "MTR"
    assert body["delivery"] == ["in_person", "online"] and body["max_credits"] == 18 and body["updated_at"]
    body = alex.put("/me/preferences", json={"max_credits": 15, "flexibility": "strict"}).json()
    assert (body["preferred_time"], body["max_credits"], body["flexibility"]) == ("midday", 15, "strict")


@pytest.mark.parametrize("body", [{"preferred_time": "noon"}, {"preferred_days": "MS"}, {"max_credits": 25},
                                  {"min_credits": -1}, {"delivery": []}, {"delivery": ["hybrid"]},
                                  {"flexibility": "rigid"}])
def test_preferences_validation(alex, body):
    response = alex.put("/me/preferences", json=body)
    assert response.status_code == 422 and response.json() == {"error": "invalid_request"}


def test_preferences_credit_range(alex):
    response = alex.put("/me/preferences", json={"min_credits": 19})
    assert response.status_code == 422 and response.json() == {"error": "invalid_credit_range"}
    assert alex.put("/me/preferences", json={"min_credits": 15, "max_credits": 15}).json()["min_credits"] == 15


# --- settings -----------------------------------------------------------------------------------------

def test_settings_default_and_partial_updates(alex):
    assert alex.get("/me/settings").json() == {**planning.DEFAULT_SETTINGS, "updated_at": None}
    body = alex.put("/me/settings", json={"appearance": "dark", "reduce_motion": True, "photo": PNG}).json()
    assert body["appearance"] == "dark" and body["reduce_motion"] is True and body["photo"] == PNG
    assert body["email_notifications"] is True and body["profile_visibility"] == "advisors"
    body = alex.put("/me/settings", json={"profile_visibility": "private"}).json()
    assert body["photo"] == PNG  # left out = kept
    assert alex.put("/me/settings", json={"photo": None}).json()["photo"] is None  # null = removed


@pytest.mark.parametrize("photo", [
    "https://example.test/me.png", "data:text/html;base64,PGgxPg==", "data:image/svg+xml;base64,PHN2Zz4=",
    "data:image/png;base64,not base64!", "javascript:alert(1)",
    "data:image/png;base64," + "A" * planning.MAX_PHOTO_CHARS,
])
def test_settings_photo_must_be_a_small_image_data_url(alex, photo):
    response = alex.put("/me/settings", json={"photo": photo})
    assert response.status_code == 422 and response.json() == {"error": "invalid_request"}


@pytest.mark.parametrize("body", [{"appearance": "Dark"}, {"profile_visibility": "public"}, {"high_contrast": "maybe"}])
def test_settings_validation(alex, body):
    assert alex.put("/me/settings", json=body).status_code == 422


# --- defaults match the database, and user 5 is emptied ---------------------------------------------------

def server_default(table, name):
    column = Base.metadata.tables[table].columns[name]
    return getattr(column.server_default.arg, "text", column.server_default.arg)


def test_api_defaults_match_the_column_defaults():
    to_text = {True: "true", False: "false"}
    for name, value in planning.DEFAULT_SETTINGS.items():
        if name not in ("photo", "updated_at"):
            assert server_default("student_settings", name) == to_text.get(value, value), name
    for name in ("preferred_time", "preferred_days", "min_credits", "max_credits", "flexibility"):
        assert server_default("student_preferences", name) == str(planning.DEFAULT_PREFERENCES[name]), name
    assert server_default("student_preferences", "delivery") == "'{in_person,online}'::text[]"


def test_clearing_a_student_empties_their_planning_rows():
    class RecordingSession:
        def __init__(self):
            self.tables = []

        def execute(self, statement):
            self.tables.append(statement.table.name)

    session = RecordingSession()
    demo_seed._clear_student(session, uuid.uuid4())
    for table in ("calendar_events", "student_preferences", "student_settings", "schedules", "completed_courses"):
        assert table in session.tables


def test_preference_and_settings_rows_belong_to_one_student():
    for model in (StudentPreferences, StudentSettings):
        [key] = model.__table__.primary_key.columns
        assert key.name == "student_id" and next(iter(key.foreign_keys)).ondelete == "CASCADE"
    rules = {str(c.sqltext) for c in StudentSettings.__table__.constraints if hasattr(c, "sqltext")}
    assert "photo IS NULL OR photo LIKE 'data:image/%'" in rules
