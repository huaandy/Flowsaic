"""Entry point for the Flowsaic API. Start it with: uv run fastapi dev app/main.py"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.routers import dev

app = FastAPI(title="Flowsaic API")

# Developer test page at /dev. Not part of the contract; see app/routers/dev.py.
app.include_router(dev.router)


@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Errors are always { "error": "snake_case_code" } (AGENTS.md ground rule 6)."""
    return JSONResponse(status_code=422, content={"error": "invalid_request"})


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Nothing lives at the root yet, so send people to the dev test page."""
    return RedirectResponse("/dev")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
