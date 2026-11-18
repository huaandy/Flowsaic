"""The signed-in student's own planning data (contract, migration 0003):

- /me/events: commitments on the weekly calendar (GET, POST, PUT /{id}, DELETE /{id}).
  Fixed events block courses (checker conflict commitment_overlap); flexible ones only warn
  (commitment_overlap_flexible). Another student's event is 404 event_not_found.
- /me/preferences: scheduling preferences (GET, PUT). Defaults for AI suggest and Flow.
- /me/settings: app settings and the profile photo (GET, PUT).

A student with no preferences or settings row gets the defaults, never a 404. PUT changes only
the fields sent (a field left out keeps its value); for settings, "photo": null removes the photo.
"""

import re
import uuid
from datetime import datetime, time
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.auth import ApiError, current_student_id
from app.db import SessionLocal
from app.models import CalendarEvent, StudentPreferences, StudentSettings
from app.normalize import DAY_ORDER

router = APIRouter(prefix="/me", tags=["me"])

HHMM_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
MAX_EVENTS = 60
# ~1 MB of image as base64 is ~1.37 million characters.
MAX_PHOTO_CHARS = 1_400_000
PHOTO_RE = re.compile(r"^data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/]+=*$")

DEFAULT_PREFERENCES = {
    "preferred_time": "none", "preferred_days": "", "min_credits": 12, "max_credits": 18,
    "delivery": ["in_person", "online"], "flexibility": "balanced", "updated_at": None,
}
DEFAULT_SETTINGS = {
    "email_notifications": True, "push_notifications": True, "advisor_updates": True, "schedule_alerts": True,
    "appearance": "light", "high_contrast": False, "larger_text": False, "reduce_motion": False,
    "profile_visibility": "advisors", "photo": None, "updated_at": None,
}

Category = Literal["work", "personal_study", "extracurricular"]
PreferredTime = Literal["morning", "midday", "afternoon", "evening", "none"]
Delivery = Literal["in_person", "online"]


def _clock(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def ordered_days(text: str) -> str:
    letters = set(text.upper())
    return "".join(d for d in DAY_ORDER if d in letters)


# --- events -----------------------------------------------------------------------------------

class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    day: Literal["M", "T", "W", "R", "F"] = Field(description="One letter, R = Thursday")
    start_time: str = Field(pattern=HHMM_PATTERN, description="HH:MM, 24-hour")
    end_time: str = Field(pattern=HHMM_PATTERN)
    location: str | None = Field(default=None, max_length=120)
    category: Category = "personal_study"
    recurrence: Literal["none", "weekly"] = "weekly"
    priority: Literal["low", "normal", "high"] = "normal"
    fixed: bool = Field(default=False, description="true = courses can't overlap it (a conflict)")

    @field_validator("title", "location")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None

    @model_validator(mode="after")
    def check(self) -> "EventIn":
        if not self.title:
            raise ValueError("title is empty")
        if self.start_time >= self.end_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventOut(BaseModel):
    id: uuid.UUID
    title: str
    day: str
    start_time: str
    end_time: str
    location: str | None
    category: str
    recurrence: str
    priority: str
    fixed: bool
    created_at: datetime
    updated_at: datetime


def _event_out(event: CalendarEvent) -> dict:
    return {
        "id": event.id, "title": event.title, "day": event.day,
        "start_time": event.start_time.strftime("%H:%M"), "end_time": event.end_time.strftime("%H:%M"),
        "location": event.location, "category": event.category, "recurrence": event.recurrence,
        "priority": event.priority, "fixed": event.fixed, "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def _event_values(body: EventIn) -> dict:
    values = body.model_dump()
    values["start_time"], values["end_time"] = _clock(body.start_time), _clock(body.end_time)
    return values


def list_events(student_id: uuid.UUID) -> list[dict]:
    with SessionLocal() as session:
        events = session.scalars(select(CalendarEvent).where(CalendarEvent.student_id == student_id)).all()
        rows = [_event_out(e) for e in events]
    return sorted(rows, key=lambda e: (DAY_ORDER.index(e["day"]), e["start_time"], e["title"]))


def create_event(student_id: uuid.UUID, body: EventIn) -> dict:
    with SessionLocal.begin() as session:
        count = session.scalar(select(func.count()).select_from(CalendarEvent)
                               .where(CalendarEvent.student_id == student_id))
        if count >= MAX_EVENTS:
            raise ApiError(422, "too_many_events")
        event = CalendarEvent(student_id=student_id, **_event_values(body))
        session.add(event)
        session.flush()
        session.refresh(event)
        return _event_out(event)


def update_event(student_id: uuid.UUID, event_id: uuid.UUID, body: EventIn) -> dict:
    with SessionLocal.begin() as session:
        event = session.scalar(select(CalendarEvent).where(CalendarEvent.id == event_id,
                                                           CalendarEvent.student_id == student_id))
        if event is None:
            raise ApiError(404, "event_not_found")
        for key, value in _event_values(body).items():
            setattr(event, key, value)
        event.updated_at = func.now()
        session.flush()
        session.refresh(event)
        return _event_out(event)


def delete_event(student_id: uuid.UUID, event_id: uuid.UUID) -> None:
    with SessionLocal.begin() as session:
        result = session.execute(delete(CalendarEvent).where(CalendarEvent.id == event_id,
                                                             CalendarEvent.student_id == student_id))
        if result.rowcount == 0:
            raise ApiError(404, "event_not_found")


@router.get("/events", response_model=list[EventOut])
def my_events(student_id: uuid.UUID = Depends(current_student_id)):
    return list_events(student_id)


@router.post("/events", status_code=201, response_model=EventOut)
def add_event(body: EventIn, student_id: uuid.UUID = Depends(current_student_id)):
    return create_event(student_id, body)


@router.put("/events/{event_id}", response_model=EventOut)
def change_event(event_id: uuid.UUID, body: EventIn, student_id: uuid.UUID = Depends(current_student_id)):
    return update_event(student_id, event_id, body)


@router.delete("/events/{event_id}", status_code=204)
def remove_event(event_id: uuid.UUID, student_id: uuid.UUID = Depends(current_student_id)) -> Response:
    delete_event(student_id, event_id)
    return Response(status_code=204)


# --- preferences ------------------------------------------------------------------------------

class PreferencesOut(BaseModel):
    preferred_time: PreferredTime
    preferred_days: str = Field(description="Letters from MTWRF; empty = no preference")
    min_credits: int
    max_credits: int
    delivery: list[Delivery]
    flexibility: Literal["flexible", "balanced", "strict"]
    updated_at: datetime | None = Field(description="null = never saved (these are the defaults)")


class PreferencesIn(BaseModel):
    """Only the fields sent change."""

    preferred_time: PreferredTime | None = None
    preferred_days: str | None = Field(default=None, pattern=r"^[MTWRFmtwrf]{0,5}$")
    min_credits: int | None = Field(default=None, ge=0, le=21)
    max_credits: int | None = Field(default=None, ge=1, le=21)
    delivery: list[Delivery] | None = Field(default=None, min_length=1, max_length=2)
    flexibility: Literal["flexible", "balanced", "strict"] | None = None


def _preferences_out(row: StudentPreferences | None) -> dict:
    if row is None:
        return dict(DEFAULT_PREFERENCES)
    return {"preferred_time": row.preferred_time, "preferred_days": row.preferred_days,
            "min_credits": row.min_credits, "max_credits": row.max_credits, "delivery": list(row.delivery),
            "flexibility": row.flexibility, "updated_at": row.updated_at}


def load_preferences(student_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        return _preferences_out(session.get(StudentPreferences, student_id))


def store_preferences(student_id: uuid.UUID, values: dict) -> dict:
    with SessionLocal.begin() as session:
        statement = insert(StudentPreferences).values(student_id=student_id, **values)
        session.execute(statement.on_conflict_do_update(
            index_elements=[StudentPreferences.student_id], set_={**values, "updated_at": func.now()}))
        return _preferences_out(session.get(StudentPreferences, student_id, populate_existing=True))


def merge_preferences(current: dict, body: PreferencesIn) -> dict:
    """The full row after applying the fields sent. 422 invalid_credit_range if min > max."""
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_days" in changes:
        changes["preferred_days"] = ordered_days(changes["preferred_days"])
    if "delivery" in changes:
        changes["delivery"] = [d for d in ("in_person", "online") if d in changes["delivery"]]
    merged = {k: v for k, v in {**current, **changes}.items() if k != "updated_at"}
    if merged["min_credits"] > merged["max_credits"]:
        raise ApiError(422, "invalid_credit_range")
    return merged


@router.get("/preferences", response_model=PreferencesOut)
def my_preferences(student_id: uuid.UUID = Depends(current_student_id)):
    return load_preferences(student_id)


@router.put("/preferences", response_model=PreferencesOut)
def save_preferences(body: PreferencesIn, student_id: uuid.UUID = Depends(current_student_id)):
    return store_preferences(student_id, merge_preferences(load_preferences(student_id), body))


# --- settings ---------------------------------------------------------------------------------

class SettingsOut(BaseModel):
    email_notifications: bool
    push_notifications: bool
    advisor_updates: bool
    schedule_alerts: bool
    appearance: Literal["light", "dark", "system"]
    high_contrast: bool
    larger_text: bool
    reduce_motion: bool
    profile_visibility: Literal["private", "advisors", "community"]
    photo: str | None = Field(description="An image data URL, or null")
    updated_at: datetime | None = Field(description="null = never saved (these are the defaults)")


class SettingsIn(BaseModel):
    """Only the fields sent change. "photo": null removes the photo."""

    email_notifications: bool | None = None
    push_notifications: bool | None = None
    advisor_updates: bool | None = None
    schedule_alerts: bool | None = None
    appearance: Literal["light", "dark", "system"] | None = None
    high_contrast: bool | None = None
    larger_text: bool | None = None
    reduce_motion: bool | None = None
    profile_visibility: Literal["private", "advisors", "community"] | None = None
    photo: str | None = Field(default=None, max_length=MAX_PHOTO_CHARS,
                              description="data:image/png|jpeg|gif|webp;base64,... (at most ~1 MB)")

    @field_validator("photo")
    @classmethod
    def image_data_url(cls, value: str | None) -> str | None:
        if value is not None and not PHOTO_RE.match(value):
            raise ValueError("photo must be a base64 image data URL (png, jpeg, gif or webp)")
        return value


SETTINGS_FIELDS = [name for name in DEFAULT_SETTINGS if name != "updated_at"]


def _settings_out(row: StudentSettings | None) -> dict:
    if row is None:
        return dict(DEFAULT_SETTINGS)
    return {**{name: getattr(row, name) for name in SETTINGS_FIELDS}, "updated_at": row.updated_at}


def load_settings(student_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        return _settings_out(session.get(StudentSettings, student_id))


def store_settings(student_id: uuid.UUID, values: dict) -> dict:
    with SessionLocal.begin() as session:
        statement = insert(StudentSettings).values(student_id=student_id, **values)
        session.execute(statement.on_conflict_do_update(
            index_elements=[StudentSettings.student_id], set_={**values, "updated_at": func.now()}))
        return _settings_out(session.get(StudentSettings, student_id, populate_existing=True))


def merge_settings(current: dict, body: SettingsIn) -> dict:
    sent = body.model_dump(exclude_unset=True)
    changes = {k: v for k, v in sent.items() if v is not None or k == "photo"}
    return {k: v for k, v in {**current, **changes}.items() if k != "updated_at"}


@router.get("/settings", response_model=SettingsOut)
def my_settings(student_id: uuid.UUID = Depends(current_student_id)):
    return load_settings(student_id)


@router.put("/settings", response_model=SettingsOut)
def save_settings(body: SettingsIn, student_id: uuid.UUID = Depends(current_student_id)):
    return store_settings(student_id, merge_settings(load_settings(student_id), body))
