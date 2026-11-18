"""The student's name from the mySAU audit (Nov 18): saved as "First Last", put back to the
placeholder when users 4 and 5 are emptied, and given to Flow (first name only).
Fake sessions; no database, no Gemini. The audit is FAKE (tests/test_audit_parser.py)."""

import uuid
from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app import demo_seed
from app.advisor import UNKNOWN_NAME, build_student_record, first_name_for, run_flow
from app.mysau import audit_store
from app.mysau.audit_parser import parse_lines
from tests.test_advisor import FakeClient, all_text, make_data, text_response
from tests.test_audit_parser import fake_lines


class RecordingSession:
    """Records every statement; get() finds any student."""

    def __init__(self, student_id=None):
        self.statements = []
        self.student_id = student_id

    def get(self, model, key):
        return SimpleNamespace(id=key)

    def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(rowcount=1)

    def scalar(self, statement):
        self.statements.append(statement)
        return self.student_id

    def add_all(self, rows):
        list(rows)

    @contextmanager
    def begin(self):
        yield self

    def updates(self, table):
        """The SET values of every UPDATE on the table, as {column: value}."""
        found = []
        for statement in self.statements:
            if statement.is_dml and getattr(statement, "table", None) is not None and \
                    statement.table.name == table and statement.__visit_name__ == "update":
                params = statement.compile(dialect=postgresql.dialect()).params
                found.append({key: value for key, value in params.items() if not key.startswith("id_")})
        return found


def fake_session_maker(session):
    @contextmanager
    def begin():
        yield session

    @contextmanager
    def plain():
        yield session

    maker = lambda: plain()  # noqa: E731
    maker.begin = begin
    return maker


# --- saving the name --------------------------------------------------------------------------------

def test_connect_saves_first_and_last_name(monkeypatch):
    session = RecordingSession()
    monkeypatch.setattr(audit_store, "SessionLocal", fake_session_maker(session))
    audit_store.save_audit(uuid.uuid4(), parse_lines(fake_lines()))
    [values] = session.updates("students")
    assert values["name"] == "Testy Fakerson"
    assert "email" not in values and "password" not in values  # never touched


def test_an_audit_without_a_name_keeps_the_current_one(monkeypatch):
    session = RecordingSession()
    monkeypatch.setattr(audit_store, "SessionLocal", fake_session_maker(session))
    parsed = parse_lines([line for line in fake_lines() if not line.text.startswith("Name:")])
    audit_store.save_audit(uuid.uuid4(), parsed)
    [values] = session.updates("students")
    assert "name" not in values


# --- placeholder names come back -------------------------------------------------------------------

def test_emptying_user_5_puts_the_placeholder_name_back(monkeypatch):
    session = RecordingSession(student_id=uuid.uuid4())
    monkeypatch.setattr(demo_seed, "SessionLocal", fake_session_maker(session))
    assert demo_seed.clear_new_student() is True
    [values] = session.updates("students")
    assert values["name"] == demo_seed.NEW_STUDENT_NAME


def test_clearing_without_a_placeholder_keeps_the_name():
    session = RecordingSession()
    demo_seed._clear_student(session, uuid.uuid4())
    [values] = session.updates("students")
    assert "name" not in values


def test_seed_runs_never_overwrite_a_connected_name():
    """_upsert_placeholder only resets the password of an existing user 4 or 5."""
    session = RecordingSession(student_id=uuid.uuid4())
    demo_seed._upsert_placeholder(session, demo_seed.RETURNING_STUDENT_NAME, demo_seed.RETURNING_STUDENT_EMAIL)
    [statement] = session.statements
    sql = str(statement.compile(dialect=postgresql.dialect()))
    conflict_part = sql.split("ON CONFLICT", 1)[1]
    assert "password" in conflict_part and "name" not in conflict_part


# --- Flow gets the first name ----------------------------------------------------------------------

def student(name, email="someone@demo.flowsaic.test"):
    return SimpleNamespace(name=name, email=email)


def test_first_name_for_real_and_placeholder_names():
    assert first_name_for(student("Alex Rivera")) == "Alex"
    assert first_name_for(student("Testy Fakerson", demo_seed.NEW_STUDENT_EMAIL)) == "Testy"  # connected user 5
    assert first_name_for(student(demo_seed.NEW_STUDENT_NAME, demo_seed.NEW_STUDENT_EMAIL)) == UNKNOWN_NAME
    assert first_name_for(student(demo_seed.RETURNING_STUDENT_NAME, demo_seed.RETURNING_STUDENT_EMAIL)) == UNKNOWN_NAME
    assert first_name_for(student("  ")) == UNKNOWN_NAME


def test_the_record_gives_flow_the_first_name_only():
    record = build_student_record(make_data())
    assert "First name: Alex" in record
    unknown = make_data()
    unknown.first_name = UNKNOWN_NAME
    assert "First name: not known yet" in build_student_record(unknown)


def test_flow_sends_the_first_name_but_no_other_identity():
    client = FakeClient([text_response("Hi Alex! Let's plan Spring 2027.")])
    result = run_flow(make_data(), "Hello", [], client=client, model="test-model")
    assert result["reply"] == "Hi Alex! Let's plan Spring 2027."
    sent = all_text(client.models.requests[0])
    assert "First name: Alex" in sent
    for private in ("Rivera", "@demo.flowsaic.test", "student_id"):
        assert private not in sent


def test_an_old_first_name_token_is_still_filled_in():
    client = FakeClient([text_response("Hi {first_name}!")])
    assert run_flow(make_data(), "Hello", [], client=client, model="m")["reply"] == "Hi Alex!"
