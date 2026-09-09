"""DuckDB connection management.

DuckDB permits a single writer per database file, so this module hands out one
process-wide connection guarded by a re-entrant lock. Every write goes through
:func:`cursor`; concurrent FastAPI worker threads serialize on the lock rather
than colliding on the file.

The corollary is operational and worth knowing: the rebuild CLI cannot open the
file while a server holds it. `app/warehouse/rebuild.py` catches that and says
so.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from app.config import get_settings

_lock = threading.RLock()
_conn: duckdb.DuckDBPyConnection | None = None
_conn_path: str | None = None


class WarehouseError(RuntimeError):
    """Any failure reaching or writing the warehouse.

    Callers on the write path catch this and mark the warehouse stale — a
    warehouse problem must never fail a ledger write.
    """


#: What to tell someone whose command lost the race for the write lock. Shared
#: by every command-line entry point that writes the warehouse (the seed and
#: the rebuild), so they cannot drift apart.
LOCKED_HINT = """
The warehouse file is held by another process — most likely a running API
server (uvicorn), which keeps the DuckDB connection open for write-through.

Either stop the server and re-run this command, or rebuild in-process:

    curl -X POST localhost:8000/api/v1/warehouse/rebuild
"""


def is_locked(exc: BaseException) -> bool:
    """Whether this failure is DuckDB's single-writer lock, not a real fault.

    Matched on the message because DuckDB raises a generic IOException for it;
    there is no distinct exception type to catch.
    """
    message = str(exc).lower()
    return "lock" in message or "being used" in message


def warehouse_path() -> str:
    return get_settings().warehouse_path


def connect(path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Return the shared connection, opening and initializing it on first use."""
    global _conn, _conn_path
    target = path or warehouse_path()
    with _lock:
        if _conn is not None and _conn_path == target:
            return _conn
        if _conn is not None:
            _conn.close()
        resolved = Path(target)
        if resolved.parent and str(resolved.parent) not in ("", "."):
            resolved.parent.mkdir(parents=True, exist_ok=True)
        try:
            _conn = duckdb.connect(str(resolved))
        except (duckdb.IOException, duckdb.Error) as exc:  # pragma: no cover - env specific
            raise WarehouseError(f"Cannot open warehouse at {target}: {exc}") from exc
        _conn_path = target

        from app.warehouse import ddl

        ddl.initialize(_conn)
        return _conn


@contextmanager
def cursor(path: str | None = None) -> Iterator[duckdb.DuckDBPyConnection]:
    """Hold the write lock for the duration of a unit of work."""
    with _lock:
        yield connect(path)


def reset(path: str | None = None) -> None:
    """Point the module at a different file (tests) and drop the old handle."""
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _conn_path = None
    if path is not None:
        connect(path)


def close() -> None:
    reset(None)
