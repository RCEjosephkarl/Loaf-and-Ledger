"""The seed writes both stores, and the warehouse half can lose a race.

DuckDB allows one writer per file, so running the seed while an API server is
up cannot load the warehouse. That is a real constraint of the store, not a
bug — but the ledger half still succeeds, so the command must say so and point
at a way to finish rather than dumping a traceback over a seed that worked.
"""

from __future__ import annotations

import app.seed as seed_module
from app.warehouse.engine import LOCKED_HINT, WarehouseError, is_locked

DUCKDB_LOCK_MESSAGE = (
    'Cannot open warehouse at ./warehouse.duckdb: IO Error: Could not set lock on file '
    '"/x/warehouse.duckdb": Conflicting lock is held in /usr/bin/python3.12 (PID 1)'
)


class TestIsLocked:
    def test_recognizes_duckdbs_lock_error(self):
        assert is_locked(WarehouseError(DUCKDB_LOCK_MESSAGE))

    def test_recognizes_the_windows_phrasing(self):
        assert is_locked(WarehouseError("The process cannot access the file, it is being used"))

    def test_does_not_swallow_unrelated_failures(self):
        assert not is_locked(WarehouseError("no such table: fact_ledger_line"))


class TestSeedUnderLock:
    def test_ledger_is_seeded_and_the_hint_is_printed(self, db_session, monkeypatch, capsys):
        """A locked warehouse must not lose the ledger seed."""
        monkeypatch.setattr(seed_module, "SessionLocal", lambda: db_session)
        monkeypatch.setattr(db_session, "close", lambda: None)

        from app.warehouse import etl

        def _locked(*_args, **_kwargs):
            raise WarehouseError(DUCKDB_LOCK_MESSAGE)

        monkeypatch.setattr(etl, "rebuild_all", _locked)

        assert seed_module.main() == 1, "a half-done seed must not report success"

        captured = capsys.readouterr()
        # The ledger half ran and is reported...
        assert "Ledger seeded:" in captured.out
        assert "journal_entries" in captured.out
        # ...and the failure explains the actual remedy.
        assert "warehouse load failed" in captured.err
        assert "POST" in LOCKED_HINT or "curl" in captured.err
        assert "stop the server" in captured.err.lower()

        # And the entries really are committed, not rolled back.
        from app.models.journal import JournalEntry

        assert db_session.query(JournalEntry).count() > 0

    def test_a_non_lock_failure_points_at_the_rebuild_command(
        self, db_session, monkeypatch, capsys
    ):
        monkeypatch.setattr(seed_module, "SessionLocal", lambda: db_session)
        monkeypatch.setattr(db_session, "close", lambda: None)

        from app.warehouse import etl

        def _broken(*_args, **_kwargs):
            raise WarehouseError("disk is full")

        monkeypatch.setattr(etl, "rebuild_all", _broken)

        assert seed_module.main() == 1
        err = capsys.readouterr().err
        assert "app.warehouse.rebuild" in err
        assert "stop the server" not in err.lower(), "a full disk is not a lock"


def test_seed_succeeds_and_loads_the_warehouse(db_session, monkeypatch, capsys):
    monkeypatch.setattr(seed_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    assert seed_module.main() == 0
    out = capsys.readouterr().out
    assert "Ledger seeded:" in out
    assert "Warehouse loaded:" in out

    from app.warehouse.engine import cursor

    with cursor() as conn:
        assert conn.execute("SELECT count(*) FROM fact_ledger_line").fetchone()[0] > 0
