"""Star-schema DDL. Idempotent — safe to run on every connect.

Grain, stated once so the queries never have to guess:

* ``fact_ledger_line``  — one row per journal line (the atomic fact).
* ``fact_payslip_item`` — one row per line of a saved salary breakdown.
* ``agg_monthly_account``, ``agg_daily_cashflow`` — materialized rollups of
  the atomic fact, refreshed for the periods a write touches.
"""

from __future__ import annotations

import duckdb

DATE_DIM_START = "2020-01-01"
DATE_DIM_END = "2035-12-31"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,   -- YYYYMMDD
    full_date     DATE      NOT NULL,
    year          SMALLINT  NOT NULL,
    quarter       TINYINT   NOT NULL,
    month         TINYINT   NOT NULL,
    month_key     INTEGER   NOT NULL,    -- YYYYMM
    month_name    VARCHAR   NOT NULL,
    month_start   DATE      NOT NULL,
    day           TINYINT   NOT NULL,
    day_of_week   TINYINT   NOT NULL,    -- 0 = Sunday
    day_name      VARCHAR   NOT NULL,
    iso_week      TINYINT   NOT NULL,
    is_weekend    BOOLEAN   NOT NULL,
    is_month_end  BOOLEAN   NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_account (
    account_key    BIGINT PRIMARY KEY,   -- mirrors the OLTP account id
    account_id     BIGINT  NOT NULL,
    code           VARCHAR NOT NULL,
    name           VARCHAR NOT NULL,
    type           VARCHAR NOT NULL,     -- asset|liability|equity|income|expense
    subtype        VARCHAR,
    is_statutory   BOOLEAN NOT NULL,
    normal_balance VARCHAR NOT NULL,     -- dr|cr
    flow_class     VARCHAR NOT NULL,     -- inflow|outflow|balance
    is_active      BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_payee (
    payee_key BIGINT PRIMARY KEY,
    payee_id  BIGINT  NOT NULL,
    name      VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_source (
    source_key INTEGER PRIMARY KEY,
    source     VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_ledger_line (
    line_id       BIGINT PRIMARY KEY,
    entry_id      BIGINT    NOT NULL,
    date_key      INTEGER   NOT NULL,
    occurred_at   TIMESTAMP NOT NULL,
    account_key   BIGINT    NOT NULL,
    payee_key     BIGINT,
    source_key    INTEGER   NOT NULL,
    debit         DECIMAL(14,2) NOT NULL,
    credit        DECIMAL(14,2) NOT NULL,
    -- Signed in the direction the account naturally grows, so summing the
    -- column gives a balance without re-deriving normal balance per row.
    signed_amount DECIMAL(14,2) NOT NULL,
    amount        DECIMAL(14,2) NOT NULL,   -- absolute magnitude
    -- True when no line of the parent entry touches income or expense: a
    -- movement between balance-sheet accounts. Every earning/spending query
    -- filters this out, which is what keeps savings from reading as spending.
    is_transfer   BOOLEAN   NOT NULL,
    memo          VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_payslip_item (
    payslip_item_id VARCHAR PRIMARY KEY,   -- "<profile_id>:<item_key>"
    profile_id      BIGINT  NOT NULL,
    date_key        INTEGER NOT NULL,
    tax_year        SMALLINT NOT NULL,
    pay_period      VARCHAR NOT NULL,
    item_key        VARCHAR NOT NULL,
    item_label      VARCHAR NOT NULL,
    kind            VARCHAR NOT NULL,      -- gross|tax|social|net|info
    amount          DECIMAL(14,2) NOT NULL,        -- period amount
    amount_annual   DECIMAL(14,2) NOT NULL,
    is_active       BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS agg_monthly_account (
    month_key   INTEGER NOT NULL,
    account_key BIGINT  NOT NULL,
    inflow      DECIMAL(14,2) NOT NULL,
    outflow     DECIMAL(14,2) NOT NULL,
    net_amount  DECIMAL(14,2) NOT NULL,
    entry_count INTEGER NOT NULL,
    PRIMARY KEY (month_key, account_key)
);

CREATE TABLE IF NOT EXISTS agg_daily_cashflow (
    date_key           INTEGER PRIMARY KEY,
    inflow             DECIMAL(14,2) NOT NULL,
    outflow            DECIMAL(14,2) NOT NULL,
    net                DECIMAL(14,2) NOT NULL,
    cumulative_balance DECIMAL(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_watermark (
    table_name     VARCHAR PRIMARY KEY,
    last_loaded_at TIMESTAMP,
    source_rows    BIGINT,
    target_rows    BIGINT,
    is_stale       BOOLEAN NOT NULL DEFAULT FALSE,
    note           VARCHAR
);
"""

FACT_TABLES = (
    "fact_ledger_line",
    "fact_payslip_item",
    "agg_monthly_account",
    "agg_daily_cashflow",
)
#: Dimensions rebuilt from the OLTP tables. `dim_date` and `dim_source` are
#: static (a generated calendar and a fixed enum) and are never truncated —
#: facts join to them, so emptying them would silently zero every query.
DIM_TABLES = ("dim_account", "dim_payee")


def initialize(conn: duckdb.DuckDBPyConnection) -> None:
    """Create every table and populate the static dimensions."""
    conn.execute(SCHEMA)
    _seed_dim_date(conn)
    _seed_dim_source(conn)


def _seed_dim_date(conn: duckdb.DuckDBPyConnection) -> None:
    """Generate the calendar once. Cheap (≈5,800 rows) and makes every
    time-series query a join rather than date arithmetic in Python."""
    if conn.execute("SELECT count(*) FROM dim_date").fetchone()[0] > 0:
        return
    conn.execute(
        f"""
        INSERT INTO dim_date
        SELECT
            CAST(strftime(d, '%Y%m%d') AS INTEGER)          AS date_key,
            d                                                AS full_date,
            CAST(year(d) AS SMALLINT)                        AS year,
            CAST(quarter(d) AS TINYINT)                      AS quarter,
            CAST(month(d) AS TINYINT)                        AS month,
            CAST(strftime(d, '%Y%m') AS INTEGER)             AS month_key,
            strftime(d, '%B')                                AS month_name,
            date_trunc('month', d)                           AS month_start,
            CAST(day(d) AS TINYINT)                          AS day,
            CAST(dayofweek(d) AS TINYINT)                    AS day_of_week,
            strftime(d, '%A')                                AS day_name,
            CAST(week(d) AS TINYINT)                         AS iso_week,
            dayofweek(d) IN (0, 6)                           AS is_weekend,
            d = (date_trunc('month', d) + INTERVAL 1 MONTH - INTERVAL 1 DAY) AS is_month_end
        FROM generate_series(DATE '{DATE_DIM_START}', DATE '{DATE_DIM_END}', INTERVAL 1 DAY) AS t(d)
        """
    )


def _seed_dim_source(conn: duckdb.DuckDBPyConnection) -> None:
    from app.models.base import EntrySource

    for i, source in enumerate(EntrySource, start=1):
        conn.execute(
            "INSERT INTO dim_source (source_key, source) SELECT ?, ? "
            "WHERE NOT EXISTS (SELECT 1 FROM dim_source WHERE source_key = ?)",
            [i, source.value, i],
        )


def source_key(source) -> int:  # noqa: ANN001
    from app.models.base import EntrySource

    value = source.value if isinstance(source, EntrySource) else str(source)
    return list(EntrySource).index(EntrySource(value)) + 1


def truncate_all(conn: duckdb.DuckDBPyConnection) -> None:
    """Empty the facts, rollups and mutable dimensions for a full reload.
    `dim_date` and `dim_source` are static and survive."""
    for table in (*FACT_TABLES, *DIM_TABLES):
        conn.execute(f"DELETE FROM {table}")
