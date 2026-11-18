"""Entry point for the Flowsaic API. Start it with: uv run fastapi dev app/main.py"""

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

import logging

from app import demo_seed, refresh
from app.auth import ApiError
from app.config import get_settings
from app.routers import ai, auth, catalog, connect, data, dev, lab, me, planning, schedules

STATIC_DIR = Path(__file__).resolve().parent / "static"
log = logging.getLogger(__name__)


def clear_new_student_on_startup() -> None:
    """User 5 (New Student) starts every backend run empty. Never raises."""
    try:
        if demo_seed.clear_new_student():
            log.info("user 5 (New Student) emptied for this run")
    except Exception as error:  # e.g. the database isn't up yet; sign-in clears them too
        log.warning("couldn't empty user 5 at startup (%s)", type(error).__name__)


def mark_interrupted_runs_on_startup() -> None:
    """A run still 'running' when the backend starts was cut off (a restart, a closed window),
    so the page polling it gets 'failed' instead of waiting forever. Runs on every start, even
    with PUBLIC_REFRESH_ON_STARTUP off (fixed Nov 18: a cut-off audit stayed 'running'). Never raises."""
    try:
        count = refresh.mark_interrupted_runs()
        if count:
            log.info("%s cut-off refresh runs marked failed", count)
    except Exception as error:  # e.g. the database isn't up yet
        log.warning("couldn't check for cut-off runs at startup (%s)", type(error).__name__)


def startup_runs() -> None:
    """In order, in one background thread: mark cut-off runs failed first, so the refresh
    started next (which creates new 'running' rows) is never caught by it."""
    mark_interrupted_runs_on_startup()
    refresh.startup_refresh()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refresh public catalog data in the background if it is stale. Startup never waits:
    # even the database check runs in the thread.
    threading.Thread(target=startup_runs, name="startup-refresh", daemon=True).start()
    threading.Thread(target=clear_new_student_on_startup, name="clear-new-student", daemon=True).start()
    yield


app = FastAPI(title="Flowsaic API", lifespan=lifespan)

# The React dev server may call the API directly with the session cookie. Exact origins only,
# never "*" (ground rule 9). Through the Vite proxy (/api) the browser sees one origin anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(planning.router)
app.include_router(catalog.router)
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
