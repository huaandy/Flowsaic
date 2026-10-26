from fastapi import FastAPI

from app.config import get_settings
from app.routers import health


def create_app() -> FastAPI:
    settings = get_settings()
    is_production = settings.environment == "production"

    app = FastAPI(
        title="Flowsaic API",
        # Interactive docs are for development only. In production they would
        # hand attackers a map of every endpoint, so they're switched off.
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )
    app.include_router(health.router)
    return app


app = create_app()
