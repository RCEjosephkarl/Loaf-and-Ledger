"""CLI: full reload of the warehouse from the OLTP journal.

    uv run python -m app.warehouse.rebuild

DuckDB allows one writer per file, so this cannot run while the API server has
the warehouse open. That is a real constraint of the chosen store, not a bug —
the message below says what to do instead.
"""

from __future__ import annotations

import sys

from app.db import SessionLocal
from app.warehouse import etl
from app.warehouse.engine import LOCKED_HINT, WarehouseError, is_locked


def main() -> int:
    db = SessionLocal()
    try:
        counts = etl.rebuild_all(db)
    except WarehouseError as exc:
        print(f"Rebuild failed: {exc}", file=sys.stderr)
        if is_locked(exc):
            print(LOCKED_HINT, file=sys.stderr)
        return 1
    finally:
        db.close()

    width = max(len(k) for k in counts)
    print("Warehouse rebuilt:")
    for table, count in counts.items():
        print(f"  {table:<{width}}  {count:>7,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
