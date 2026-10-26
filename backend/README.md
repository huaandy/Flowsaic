# Flowsaic Backend

FastAPI backend for Flowsaic. Project rules live in `../AGENTS.md`.

## Setup (Windows, PowerShell)
```powershell
cd backend
uv sync                       # installs dependencies into .venv
copy .env.example .env        # then edit .env with real values
```

## Run
```powershell
uv run fastapi dev app/main.py
```
- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs (disabled when ENVIRONMENT=production)

## Test
```powershell
uv run pytest
```

## Layout
```
app/
  main.py        creates the app, registers routers
  config.py      settings from environment variables
  db.py          database engine/session (no models yet)
  routers/       one file per feature area
tests/           pytest tests
alembic/         database migrations (none yet)
```
