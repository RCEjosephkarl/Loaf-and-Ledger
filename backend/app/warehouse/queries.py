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

from datetime import date, timedelta
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


def _series_bounds(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    """Unbounded sides follow history; explicit sides include empty dates."""
    with cursor() as conn:
        first, last = conn.execute(
            "SELECT MIN(d.full_date), MAX(d.full_date) FROM fact_ledger_line f "
            "JOIN dim_date d ON d.date_key = f.date_key"
        ).fetchone()
    return start or first, end or last


def _month_window(
    months: int | None, start: date | None, end: date | None
) -> tuple[date | None, date | None, list[str]]:
    bounded = start is not None or end is not None
    start, end = _series_bounds(start, end)
    if start is None or end is None or start > end:
        return start, end, []
    if months is not None and not bounded:
        index = end.year * 12 + end.month - months
        start = max(start, date(index // 12, index % 12 + 1, 1))
    month = start.replace(day=1)
    labels = []
    while month <= end:
        labels.append(month.strftime("%Y-%m"))
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return start, end, labels


def monthly(
    months: int | None = None,
    account_id: int | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Calendar-month totals filtered by posting dates before aggregation."""
    start, end, labels = _month_window(months, start, end)
    if not labels:
        return []
    lo, hi = _bounds(start, end)
    clause, params = _account_clause(account_id, [lo, hi])
    with cursor() as conn:
        rows = conn.execute(
            f"""
            SELECT d.month_key,
                   SUM(CASE WHEN a.flow_class = 'inflow' THEN f.signed_amount ELSE 0 END),
                   SUM(CASE WHEN a.flow_class = 'outflow' THEN f.signed_amount ELSE 0 END)
            FROM fact_ledger_line f
            JOIN dim_date d ON d.date_key = f.date_key
            JOIN dim_account a ON a.account_key = f.account_key
            WHERE f.date_key BETWEEN ? AND ? AND NOT f.is_transfer {clause}
            GROUP BY d.month_key
            """,
            params,
        ).fetchall()
    values = {f"{r[0] // 100:04d}-{r[0] % 100:02d}": r[1:] for r in rows}
    series = []
    for label in labels:
        income, expense = (_dec(v) for v in values.get(label, (ZERO, ZERO)))
        series.append(
            {"month": label, "income": income, "expense": expense, "net": money(income - expense)}
        )
    return series


def monthly_by_account(
    months: int | None = None,
    flow: str = "outflow",
    *,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    start, end, labels = _month_window(months, start, end)
    if not labels:
        return {"months": [], "series": []}
    lo, hi = _bounds(start, end)
    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT a.account_id, a.name, d.month_key, SUM(f.signed_amount)
            FROM fact_ledger_line f
            JOIN dim_account a ON a.account_key = f.account_key
            JOIN dim_date d ON d.date_key = f.date_key
            WHERE f.date_key BETWEEN ? AND ? AND a.flow_class = ? AND NOT f.is_transfer
            GROUP BY a.account_id, a.name, a.code, d.month_key
            ORDER BY a.code, d.month_key
            """,
            [lo, hi, flow],
        ).fetchall()
    index = {label: i for i, label in enumerate(labels)}
    series = {}
    for account_id, name, month_key, amount in rows:
        bucket = series.setdefault(
            account_id,
            {"account_id": account_id, "account_name": name, "values": [money(ZERO)] * len(labels)},
        )
        bucket["values"][index[f"{month_key // 100:04d}-{month_key % 100:02d}"]] = _dec(amount)
    return {"months": labels, "series": [s for s in series.values() if any(s["values"])]}


def running_balance(start: date | None = None, end: date | None = None) -> list[dict]:
    """Daily activity and cumulative balances, including days without postings."""
    start, end = _series_bounds(start, end)
    if start is None or end is None or start > end:
        return []
    lo, hi = _bounds(start, end)
    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT d.full_date, c.inflow, c.outflow, c.net
            FROM agg_daily_cashflow c JOIN dim_date d ON d.date_key = c.date_key
            WHERE c.date_key BETWEEN ? AND ? ORDER BY c.date_key
            """,
            [lo, hi],
        ).fetchall()
        previous = conn.execute(
            "SELECT cumulative_balance FROM agg_daily_cashflow WHERE date_key < ? "
            "ORDER BY date_key DESC LIMIT 1",
            [lo],
        ).fetchone()
    opening = _dec(previous[0]) if previous else ZERO
    values = {row[0]: row[1:] for row in rows}
    running = ZERO
    points = []
    day = start
    while day <= end:
        income, expense, net = (_dec(v) for v in values.get(day, (ZERO, ZERO, ZERO)))
        running = money(running + net)
        points.append(
            {
                "date": day,
                "income": income,
                "expense": expense,
                "net": net,
                "balance": running,
                "cumulative_balance": money(opening + running),
            }
        )
        day += timedelta(days=1)
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
