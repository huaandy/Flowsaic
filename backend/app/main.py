"""Entry point for the Flowsaic API. Start it with: uv run fastapi dev app/main.py"""

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app import refresh
from app.auth import ApiError
from app.routers import ai, auth, connect, data, dev, lab, me, schedules

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refresh public catalog data in the background if it is stale. Startup never waits:
    # even the database check runs in the thread.
    threading.Thread(target=refresh.startup_refresh, name="startup-refresh", daemon=True).start()
    yield


app = FastAPI(title="Flowsaic API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(schedules.router)
app.include_router(ai.router)
app.include_router(data.router)
app.include_router(connect.router)
# Developer test page at /dev. Not part of the contract; see app/routers/dev.py.
app.include_router(dev.router)
app.include_router(lab.router)  # Schedule lab tab, also not in the contract


@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Errors are always { "error": "snake_case_code" } (AGENTS.md ground rule 6)."""
    return JSONResponse(status_code=422, content={"error": "invalid_request"})


@app.exception_handler(ApiError)
def api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code})


# Prototype pages served by the backend (not Andy's React front end): sign in at /, then
# the tabbed test page at /dev (My profile, Search, Browse, Chat, Database).
@app.get("/", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/home", include_in_schema=False)
def home_page() -> RedirectResponse:
    """The profile moved into the /dev page's My profile tab."""
    return RedirectResponse("/dev")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
