"""Prototype sign-in and sessions (semester 1).

- POST /auth/login takes { email, password }. For the prototype, `email` also accepts the
  usernames 1-4 (the demo students below) and the password is NOT checked. Real accounts,
  password hashing and rate limits are semester 2 (AGENTS.md).
- A session is a random token in an HttpOnly cookie. Sessions live in this process's
  memory, so restarting the server signs everyone out. No new dependencies.
"""

import secrets
import threading
import uuid

from fastapi import Request
from sqlalchemy import func, select

from app.db import SessionLocal
from app.demo_seed import ALEX, JORDAN, NEW_STUDENT_EMAIL, SAM
from app.models import Student

SESSION_COOKIE = "flowsaic_session"

# Username shortcuts on the login page (prototype only).
DEMO_USERNAMES = {
    "1": ALEX.email,
    "2": JORDAN.email,
    "3": SAM.email,
    "4": NEW_STUDENT_EMAIL,
}

_sessions: dict[str, uuid.UUID] = {}
_sessions_lock = threading.Lock()


class ApiError(Exception):
    """Turned into { "error": code } with this status by the handler in main.py."""

    def __init__(self, status_code: int, code: str):
        super().__init__(code)
        self.status_code = status_code
        self.code = code


def login_email(username: str) -> str:
    """'1' -> Alex's email; anything else is treated as an email address."""
    value = username.strip()
    return DEMO_USERNAMES.get(value, value.lower())


def find_student_id(email: str) -> uuid.UUID | None:
    with SessionLocal() as session:
        return session.scalar(select(Student.id).where(func.lower(Student.email) == email))


def create_session(student_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = student_id
    return token


def end_session(token: str | None) -> None:
    if token:
        with _sessions_lock:
            _sessions.pop(token, None)


def current_student_id(request: Request) -> uuid.UUID:
    """FastAPI dependency: the signed-in student's id, or 401 not_authenticated."""
    token = request.cookies.get(SESSION_COOKIE)
    with _sessions_lock:
        student_id = _sessions.get(token) if token else None
    if student_id is None:
        raise ApiError(401, "not_authenticated")
    return student_id
