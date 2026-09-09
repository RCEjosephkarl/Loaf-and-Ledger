"""OLAP warehouse: a DuckDB star schema derived from the OLTP journal.

The two stores have different jobs. `app/models` is normalized and
write-optimized: it exists to accept a correct, balanced entry. This package is
denormalized and read-optimized: it exists to answer "where did the money go"
in one scan, with the dimensions (date, account, payee, source) already
resolved.

The warehouse is *derived data* — deleting warehouse.duckdb costs nothing but
a rebuild. The OLTP database is always the system of record.
"""

from app.warehouse import ddl, engine, etl, queries, status

__all__ = ["ddl", "engine", "etl", "queries", "status"]
