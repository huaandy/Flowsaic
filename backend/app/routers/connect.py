"""POST /connect/mysau: open a browser on the backend machine for a student to sign in to
mySAU, then import the course schedule and/or their degree audit.

Not among the contract's sixteen endpoints yet (added by prompt 2, Nov 17). Poll
GET /data/refresh/{id} for each returned run.
"""

import uuid
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.mysau import run as mysau_run
from app.mysau.audit_store import StudentNotFound
from app.routers.data import RunStarted

router = APIRouter(prefix="/connect", tags=["mySAU connect"])


class ConnectRequest(BaseModel):
    student_id: uuid.UUID
    fetch: list[Literal["sections", "audit"]] = Field(default=["sections", "audit"], min_length=1)


class ConnectStarted(BaseModel):
    runs: list[RunStarted]


@router.post("/mysau", status_code=202, response_model=ConnectStarted)
def connect_mysau(body: ConnectRequest):
    try:
        run_ids = mysau_run.start_connect(body.student_id, list(dict.fromkeys(body.fetch)))
    except StudentNotFound:
        return JSONResponse(status_code=404, content={"error": "student_not_found"})
    except mysau_run.ConnectAlreadyRunning:
        return JSONResponse(status_code=409, content={"error": "connect_already_running"})
    return {"runs": [{"id": run_id, "kind": kind} for kind, run_id in run_ids.items()]}
