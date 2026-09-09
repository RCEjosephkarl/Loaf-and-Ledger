"""Analytical reads against the star schema.

Every function here returns plain Python types, so the routers stay thin and
nothing above this layer needs to know that the answers come from DuckDB. The
recurring shape is a join of ``fact_ledger_line`` to ``dim_date`` and
``dim_account`` — the work the old Python aggregation loop did per row, done
once in the engine.

`is_transfer` is filtered out of every earning and spending figure. Moving
money into savings is not income and not expense; counting it as either is the
defect this schema exists to remove.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.tax.models import money
from app.warehouse.engine import cursor

ZERO = Decimal("0")


def _date_key(value: date | None, default: int) -> int:
    return value.year * 10000 + value.month * 100 + value.day if value else default


def _bounds(start: date | None, end: date | None) -> tuple[int, int]:
    return _date_key(start, 0), _date_key(end, 99999999)


def _dec(value) -> Decimal:  # noqa: ANN001
    return money(Decimal(str(value or 0)))


# ------------------------------------------------------------------ overview


def totals(
    start: date | None = None, end: date | None = None, account_id: int | None = None
) -> dict:
    """Income, expense and net cash flow over a window."""
    lo, hi = _bounds(start, end)
    clause, params = _account_clause(account_id, [lo, hi])
    with cursor() as conn:
        row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN a.flow_class = 'inflow'  THEN f.signed_amount END), 0),
                COALESCE(SUM(CASE WHEN a.flow_class = 'outflow' THEN f.signed_amount END), 0),
                COALESCE(SUM(CASE WHEN f.is_transfer AND s.source <> 'opening'
                                  THEN f.debit END), 0)
            FROM fact_ledger_line f
            JOIN dim_account a ON a.account_key = f.account_key
            JOIN dim_source  s ON s.source_key = f.source_key
            WHERE f.date_key BETWEEN ? AND ? {clause}
            """,
            params,
        ).fetchone()
    income, expense, transfers = (_dec(v) for v in row)
    return {
        "total_income": income,
        "total_expense": expense,
        "net_cashflow": money(income - expense),
        # Surfaced rather than hidden: the Analytics narrative names the money
        # that moved between your own accounts so it is visibly not "spending".
        # Opening balances are excluded — seeding a starting balance is not a
        # movement the user made during the period.
        "transfer_volume": transfers,
    }


def _account_clause(account_id: int | None, params: list) -> tuple[str, list]:
    """Restrict to entries that touch one account — the entry, not just the
    line, so an expense paid from that account keeps its expense line."""
    if account_id is None:
        return "", params
    return (
        "AND f.entry_id IN (SELECT entry_id FROM fact_ledger_line WHERE account_key = ?)",
        [*params, account_id],
    )


def by_account(
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    flow: str | None = None,
) -> list[dict]:
    """Per-account totals over a window, biggest first."""
    lo, hi = _bounds(start, end)
    clause, params = _account_clause(account_id, [lo, hi])
    flow_clause = ""
    if flow:
        flow_clause = "AND a.flow_class = ?"
        params = [*params, flow]
    with cursor() as conn:
        rows = conn.execute(
            f"""
            SELECT a.account_id, a.code, a.name, a.type, a.flow_class, a.is_statutory,
                   SUM(f.signed_amount) AS total,
                   COUNT(DISTINCT f.entry_id) AS entries
            FROM fact_ledger_line f
            JOIN dim_account a ON a.account_key = f.account_key
            WHERE f.date_key BETWEEN ? AND ?
              AND a.flow_class <> 'balance'
              AND NOT f.is_transfer
              {clause} {flow_clause}
            GROUP BY a.account_id, a.code, a.name, a.type, a.flow_class, a.is_statutory
            HAVING SUM(f.signed_amount) <> 0
            ORDER BY total DESC
            """,
            params,
        ).fetchall()
    return [
        {
            "account_id": r[0],
            "code": r[1],
            "account_name": r[2],
            "type": r[3],
            "flow_class": r[4],
            "is_statutory": bool(r[5]),
            "total": _dec(r[6]),
            "entries": int(r[7]),
        }
        for r in rows
    ]


# -------------------------------------------------------------- time series


def monthly(months: int = 6, account_id: int | None = None) -> list[dict]:
    """Trailing-N-month income vs expense, read from the monthly rollup."""
    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT m.month_key,
                   COALESCE(SUM(m.inflow), 0),
                   COALESCE(SUM(m.outflow), 0)
            FROM agg_monthly_account m
            GROUP BY m.month_key
            ORDER BY m.month_key
            """
        ).fetchall()
    series = [
        {
            "month": f"{r[0] // 100:04d}-{r[0] % 100:02d}",
            "income": _dec(r[1]),
            "expense": _dec(r[2]),
            "net": money(_dec(r[1]) - _dec(r[2])),
        }
        for r in rows
    ]
    return series[-months:]


def monthly_by_account(months: int = 6, flow: str = "outflow") -> dict:
    """Per-account monthly totals — feeds the stacked expense-mix chart."""
    with cursor() as conn:
        month_rows = conn.execute(
            "SELECT DISTINCT month_key FROM agg_monthly_account ORDER BY month_key"
        ).fetchall()
        month_keys = [r[0] for r in month_rows][-months:]
        if not month_keys:
            return {"months": [], "series": []}
        placeholders = ",".join("?" for _ in month_keys)
        column = "m.outflow" if flow == "outflow" else "m.inflow"
        rows = conn.execute(
            f"""
            SELECT a.account_id, a.name, m.month_key, {column}
            FROM agg_monthly_account m
            JOIN dim_account a ON a.account_key = m.account_key
            WHERE m.month_key IN ({placeholders}) AND a.flow_class = ?
            ORDER BY a.code, m.month_key
            """,
            [*month_keys, flow],
        ).fetchall()

    labels = [f"{k // 100:04d}-{k % 100:02d}" for k in month_keys]
    index = {k: i for i, k in enumerate(month_keys)}
    series: dict[int, dict] = {}
    for account_id, name, month_key, amount in rows:
        bucket = series.setdefault(
            account_id,
            {"account_id": account_id, "account_name": name, "values": [ZERO] * len(month_keys)},
        )
        bucket["values"][index[month_key]] = _dec(amount)
    # Drop accounts that were all zeros across the window — a legend entry for
    # a flat line at zero is noise, not information.
    kept = [s for s in series.values() if any(v != 0 for v in s["values"])]
    return {"months": labels, "series": kept}


def running_balance(start: date | None = None, end: date | None = None) -> list[dict]:
    """Daily in/out and a cumulative balance.

    `balance` restarts at the window (what the range-scoped charts show);
    `cumulative_balance` is the all-time figure the same row sits at.
    """
    lo, hi = _bounds(start, end)
    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT d.full_date, c.inflow, c.outflow, c.net, c.cumulative_balance
            FROM agg_daily_cashflow c
            JOIN dim_date d ON d.date_key = c.date_key
            WHERE c.date_key BETWEEN ? AND ?
            ORDER BY c.date_key
            """,
            [lo, hi],
        ).fetchall()
    running = ZERO
    points = []
    for full_date, inflow, outflow, net, cumulative in rows:
        running += _dec(net)
        points.append(
            {
                "date": full_date,
                "income": _dec(inflow),
                "expense": _dec(outflow),
                "net": _dec(net),
                "balance": money(running),
                "cumulative_balance": _dec(cumulative),
            }
        )
    return points


def cumulative_balance_as_of(day: date) -> Decimal:
    """All-time net cash flow up to and including `day` — the carry-over
    figure the budget "initial fund" default is built from."""
    with cursor() as conn:
        row = conn.execute(
            "SELECT cumulative_balance FROM agg_daily_cashflow WHERE date_key <= ? "
            "ORDER BY date_key DESC LIMIT 1",
            [_date_key(day, 99999999)],
        ).fetchone()
    return _dec(row[0]) if row else ZERO


# -------------------------------------------------------------- budgets


def spend_by_account(start: date, end_exclusive: date) -> dict[int, Decimal]:
    """Expense per account over [start, end) — the budget tracker's spend side."""
    lo = _date_key(start, 0)
    hi_row = end_exclusive.year * 10000 + end_exclusive.month * 100 + end_exclusive.day
    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT a.account_id, COALESCE(SUM(f.signed_amount), 0)
            FROM fact_ledger_line f
            JOIN dim_account a ON a.account_key = f.account_key
            WHERE f.date_key >= ? AND f.date_key < ?
              AND a.flow_class = 'outflow' AND NOT f.is_transfer
            GROUP BY a.account_id
            """,
            [lo, hi_row],
        ).fetchall()
    return {int(r[0]): _dec(r[1]) for r in rows}


# -------------------------------------------------------------- earnings


def earnings_breakdown(profile_id: int | None = None) -> dict:
    """The gross-to-net story for the active payslip.

    Returned in posting order — gross first, deductions in the order they were
    computed, net last — so the waterfall chart can render it without
    re-sorting or knowing PH's contribution rules.
    """
    with cursor() as conn:
        if profile_id is None:
            row = conn.execute(
                "SELECT profile_id FROM fact_payslip_item WHERE is_active LIMIT 1"
            ).fetchone()
            if row is None:
                return {"profile_id": None, "items": [], "gross": ZERO, "net": ZERO}
            profile_id = row[0]
        rows = conn.execute(
            """
            SELECT item_key, item_label, kind, amount, amount_annual, tax_year, pay_period
            FROM fact_payslip_item
            WHERE profile_id = ?
            ORDER BY CASE kind WHEN 'gross' THEN 0 WHEN 'social' THEN 1
                               WHEN 'tax' THEN 2 WHEN 'net' THEN 4 ELSE 3 END,
                     item_key
            """,
            [profile_id],
        ).fetchall()

    items = [
        {
            "key": r[0],
            "label": r[1],
            "kind": r[2],
            "amount": _dec(r[3]),
            "amount_annual": _dec(r[4]),
        }
        for r in rows
    ]
    gross = next((i["amount"] for i in items if i["kind"] == "gross"), ZERO)
    net = next((i["amount"] for i in items if i["kind"] == "net"), ZERO)
    deductions = [i for i in items if i["kind"] in ("tax", "social")]
    return {
        "profile_id": profile_id,
        "tax_year": rows[0][5] if rows else None,
        "pay_period": rows[0][6] if rows else None,
        "items": items,
        "gross": gross,
        "net": net,
        "total_deductions": money(sum((i["amount"] for i in deductions), ZERO)),
        "take_home_rate": (net / gross).quantize(Decimal("0.0001")) if gross else ZERO,
    }


# -------------------------------------------------------------- accounts


def account_balances_over_time(start: date | None = None, end: date | None = None) -> list[dict]:
    """Month-end balance per balance-sheet account."""
    lo, hi = _bounds(start, end)
    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT a.account_id, a.name, a.type, d.month_key, SUM(f.signed_amount)
            FROM fact_ledger_line f
            JOIN dim_account a ON a.account_key = f.account_key
            JOIN dim_date    d ON d.date_key = f.date_key
            WHERE f.date_key BETWEEN ? AND ? AND a.flow_class = 'balance'
            GROUP BY a.account_id, a.name, a.type, d.month_key
            ORDER BY a.account_id, d.month_key
            """,
            [lo, hi],
        ).fetchall()
    return [
        {
            "account_id": r[0],
            "account_name": r[1],
            "type": r[2],
            "month": f"{r[3] // 100:04d}-{r[3] % 100:02d}",
            "change": _dec(r[4]),
        }
        for r in rows
    ]
