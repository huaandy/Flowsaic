"""Refresh endpoints and the background runner. The database and scrapers are faked."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import refresh
from app.db import get_db
from app.main import app
from app.models import RefreshRun

client = TestClient(app)


@pytest.fixture
def fake_runs(monkeypatch):
    """Record start/finish calls instead of writing refresh_runs."""
    runs: dict[uuid.UUID, dict] = {}

    def start_run(kind, student_id=None):
        run_id = uuid.uuid4()
        runs[run_id] = {"kind": kind, "status": "running"}
        return run_id

    def finish_run(run_id, *, ok, rows_changed=None, error=None):
        runs[run_id].update(status="ok" if ok else "failed", rows_changed=rows_changed, error=error)

    monkeypatch.setattr(refresh, "start_run", start_run)
    monkeypatch.setattr(refresh, "finish_run", finish_run)
    return runs


def test_runs_degree_maps_then_course_info_and_records_each(fake_runs):
    order = []
    steps = {
        "degree_maps": lambda: order.append("degree_maps") or 12,
        "course_info": lambda: order.append("course_info") or 3,
    }
    run_ids = refresh.start_public_refresh(steps, wait=True)
    assert order == ["degree_maps", "course_info"]
    assert fake_runs[run_ids["degree_maps"]] == {"kind": "degree_maps", "status": "ok", "rows_changed": 12, "error": None}
    assert fake_runs[run_ids["course_info"]]["rows_changed"] == 3


def test_a_failed_scraper_is_recorded_and_the_next_one_still_runs(fake_runs):
    def broken():
        raise RuntimeError("bot protection on /content.php (HTTP 202)\n<html>page text</html>")

    run_ids = refresh.start_public_refresh({"degree_maps": broken, "course_info": lambda: 0}, wait=True)
    failed = fake_runs[run_ids["degree_maps"]]
    assert failed["status"] == "failed"
    assert failed["error"] == "RuntimeError: bot protection on /content.php (HTTP 202)"  # first line only
    assert fake_runs[run_ids["course_info"]]["status"] == "ok"


def test_only_one_public_refresh_at_a_time(fake_runs):
    release = threading.Event()
    steps = {"degree_maps": lambda: release.wait(5) and 0, "course_info": lambda: 0}
    refresh.start_public_refresh(steps)
    try:
        with pytest.raises(refresh.RefreshAlreadyRunning):
            refresh.start_public_refresh(steps)
        response = client.post("/data/refresh/public")
        assert response.status_code == 409
        assert response.json() == {"error": "refresh_already_running"}
    finally:
        release.set()
    refresh._public_lock.acquire(timeout=5)  # wait for the thread to finish
    refresh._public_lock.release()


def test_post_refresh_returns_one_run_per_scraper(monkeypatch):
    ids = {"degree_maps": uuid.uuid4(), "course_info": uuid.uuid4()}
    monkeypatch.setattr(refresh, "start_public_refresh", lambda: ids)
    response = client.post("/data/refresh/public")
    assert response.status_code == 202
    assert response.json() == {
        "runs": [
            {"id": str(ids["degree_maps"]), "kind": "degree_maps"},
            {"id": str(ids["course_info"]), "kind": "course_info"},
        ]
    }


class FakeSession:
    def __init__(self, run):
        self.run = run

    def get(self, model, run_id):
        return self.run if self.run and self.run.id == run_id else None


def test_get_refresh_status():
    run = RefreshRun(
        id=uuid.uuid4(), kind="course_info", status="ok", started_at=datetime(2026, 11, 17, tzinfo=UTC),
        finished_at=datetime(2026, 11, 17, 1, tzinfo=UTC), rows_changed=4, error=None, student_id=None,
    )
    app.dependency_overrides[get_db] = lambda: FakeSession(run)
    try:
        body = client.get(f"/data/refresh/{run.id}").json()
        assert body["status"] == "ok" and body["rows_changed"] == 4 and body["student_id"] is None
        missing = client.get(f"/data/refresh/{uuid.uuid4()}")
        assert missing.status_code == 404 and missing.json() == {"error": "refresh_run_not_found"}
        assert client.get("/data/refresh/not-a-uuid").json() == {"error": "invalid_request"}
    finally:
        app.dependency_overrides.clear()


def test_refresh_is_due_when_either_scraper_is_stale(monkeypatch):
    now = datetime(2026, 11, 17, tzinfo=UTC)
    finished = {"degree_maps": now - timedelta(days=1), "course_info": now - timedelta(days=8)}
    monkeypatch.setattr(refresh, "last_ok_finished", finished.get)
    assert refresh.public_refresh_due(now) is True
    finished["course_info"] = now - timedelta(days=2)
    assert refresh.public_refresh_due(now) is False
    finished["degree_maps"] = None
    assert refresh.public_refresh_due(now) is True


def test_startup_does_nothing_when_switched_off(monkeypatch):
    monkeypatch.setattr(refresh, "mark_interrupted_runs", lambda: pytest.fail("touched the database"))
    refresh.startup_refresh()  # conftest sets PUBLIC_REFRESH_ON_STARTUP=false


def test_cut_off_runs_are_marked_failed_on_every_start_before_the_refresh(monkeypatch):
    """A connect cut off by a restart must not stay 'running' (Nov 18), even with the startup
    refresh off; and the marking runs before the refresh creates new 'running' rows."""
    from app import main

    calls = []
    monkeypatch.setattr(refresh, "mark_interrupted_runs", lambda: calls.append("mark") or 1)
    monkeypatch.setattr(refresh, "startup_refresh", lambda: calls.append("refresh"))
    main.startup_runs()
    assert calls == ["mark", "refresh"]


def test_marking_cut_off_runs_never_breaks_startup(monkeypatch):
    from app import main

    def database_down():
        raise OSError("connection refused")

    monkeypatch.setattr(refresh, "mark_interrupted_runs", database_down)
    monkeypatch.setattr(refresh, "startup_refresh", lambda: None)
    main.startup_runs()  # no exception
