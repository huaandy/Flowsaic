import os

# Tests never need a real database or real keys. This lets them run without a .env file.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5433/test")
