"""Data refresh endpoints: start the public scrapers, check a refresh run's status.

Not among the contract's sixteen endpoints yet (added by prompt 2, Nov 17).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import refresh
from app.db import get_db
from app.models import RefreshRun

router = APIRouter(prefix="/data", tags=["data refresh"])


class RunStarted(BaseModel):
    id: uuid.UUID
    kind: str


class PublicRefreshStarted(BaseModel):
    runs: list[RunStarted]


class RefreshRunOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_changed: int | None
    error: str | None
    student_id: uuid.UUID | None


def error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@router.post("/refresh/public", status_code=202, response_model=PublicRefreshStarted)
def refresh_public():
    """Start the degree map and course info scrapers in the background.

    Returns one refresh_run per scraper; poll GET /data/refresh/{id}. A full course pass
    takes days, because the catalog asks for 120 seconds between requests.
    """
    try:
        run_ids = refresh.start_public_refresh()
    except refresh.RefreshAlreadyRunning:
        return error(409, "refresh_already_running")
    return {"runs": [{"id": run_id, "kind": kind} for kind, run_id in run_ids.items()]}


@router.get("/refresh/{run_id}", response_model=RefreshRunOut)
def refresh_status(run_id: uuid.UUID, session: Session = Depends(get_db)):
    run = session.get(RefreshRun, run_id)
    if run is None:
        return error(404, "refresh_run_not_found")
    return RefreshRunOut.model_validate(run, from_attributes=True)
