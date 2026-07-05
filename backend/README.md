# Loaf & Ledger — Backend

FastAPI + SQLAlchemy service. See the repository root `README.md` for the full
project write-up and `WALKTHROUGH.md` for usage.

```bash
uv sync --extra dev            # install (Python 3.12)
uv run alembic upgrade head    # create schema
uv run python -m app.seed      # seed single user + reference data + demo rows
uv run uvicorn app.main:app --reload
uv run pytest                  # unit (tax engine) + integration (API)
```

`DATABASE_URL` selects the backend (defaults to a local SQLite file for dev;
set a `postgresql+psycopg://…` URL for production).
