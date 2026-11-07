"""Section date bounds, salary selection, and pagination across complete history."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import insert

from app.models.base import EntrySource
from app.models.journal import JournalEntry, JournalLine
from app.services.journal import LineInput, post_entry
from app.tax import engine
from app.warehouse import etl


def earn(db, chart, user_id, when, amount="100"):
    return post_entry(
        db,
        user_id,
        occurred_at=when,
        lines=[
            LineInput(account_id=chart["1020"].id, debit=Decimal(amount)),
            LineInput(account_id=chart["4010"].id, credit=Decimal(amount)),
        ],
    )


def test_period_activity_keeps_prior_balance_and_includes_end_of_day(
    client, db_session, chart, user_id
):
    earn(db_session, chart, user_id, datetime(2025, 12, 31, 23, 59), "1000")
    earn(db_session, chart, user_id, datetime(2026, 1, 1), "200")
    earn(db_session, chart, user_id, datetime(2026, 1, 31, 23, 59, 59, 999999), "300")
    earn(db_session, chart, user_id, datetime(2026, 2, 1), "900")
    etl.rebuild_all(db_session)
    params = {"start": "2026-01-01", "end": "2026-01-31"}
    body = client.get("/api/v1/accounts/balances", params=params).json()
    bank = next(a for a in body["accounts"] if a["code"] == "1020")
    assert bank["debits"] == "500.00"
    assert bank["balance"] == "1500.00"
    assert body["net_worth"] == "1500.00"
    dashboard = client.get("/api/v1/dashboard/summary", params=params).json()
    assert dashboard["net_worth"] == "1500.00"
    assert dashboard["total_income"] == "500.00"
    # Legacy timestamp reads retain their original lifetime-activity meaning.
    legacy = client.get("/api/v1/accounts/balances", params={"as_of": "2026-01-01T00:00:00"})
    bank = next(a for a in legacy.json()["accounts"] if a["code"] == "1020")
    assert bank["debits"] == bank["balance"] == "1200.00"


def test_chart_calendar_bounds_and_partial_month(client, db_session, chart, user_id):
    for when in (datetime(2025, 12, 31), datetime(2026, 1, 1), datetime(2026, 1, 20)):
        earn(db_session, chart, user_id, when)
    etl.rebuild_all(db_session)
    params = {"start": "2025-11-01", "end": "2026-01-10", "months": 1}
    points = client.get("/api/v1/analytics/monthly", params=params).json()["series"]
    assert [p["month"] for p in points] == ["2025-11", "2025-12", "2026-01"]
    assert [p["income"] for p in points] == ["0.00", "100.00", "100.00"]
    mix = client.get("/api/v1/analytics/monthly-by-account", params={**params, "flow": "inflow"})
    assert mix.json()["months"] == [p["month"] for p in points]
    assert mix.json()["series"][0]["values"] == ["0.00", "100.00", "100.00"]
    daily = client.get(
        "/api/v1/analytics/running-balance",
        params={
            "start": "2026-01-02",
            "end": "2026-01-21",
        },
    ).json()["points"]
    assert len(daily) == 20
    assert daily[0]["balance"] == "0.00"
    assert daily[0]["cumulative_balance"] == "200.00"
    assert daily[-1]["balance"] == "100.00"
    assert daily[-1]["cumulative_balance"] == "300.00"
    assert daily[-1]["date"] == "2026-01-21"


def test_empty_calendar_and_all_history_over_36_months(client, db_session, chart, user_id):
    empty = client.get(
        "/api/v1/analytics/monthly",
        params={
            "start": "2026-01-01",
            "end": "2026-03-31",
        },
    ).json()["series"]
    assert len(empty) == 3 and all(p["net"] == "0.00" for p in empty)
    earn(db_session, chart, user_id, datetime(2020, 12, 31))
    earn(db_session, chart, user_id, datetime(2026, 1, 1))
    etl.rebuild_all(db_session)
    all_months = client.get("/api/v1/analytics/monthly").json()["series"]
    assert len(all_months) == 62
    assert all_months[0]["month"] == "2020-12"
    assert all_months[-1]["month"] == "2026-01"
    legacy = client.get("/api/v1/analytics/monthly", params={"months": 3}).json()["series"]
    assert len(legacy) == 3


@pytest.mark.parametrize(
    "path",
    [
        "accounts/balances",
        "dashboard/summary",
        "analytics/overview",
        "analytics/monthly",
        "analytics/monthly-by-account",
        "analytics/running-balance",
    ],
)
def test_invalid_ranges_are_rejected(client, path):
    assert (
        client.get(
            f"/api/v1/{path}",
            params={
                "start": "2026-02-01",
                "end": "2026-01-01",
            },
        ).status_code
        == 422
    )


@pytest.mark.parametrize("period,factor", [("monthly", 12), ("annual", 1), ("fortnightly", 26)])
def test_period_deductions_reconcile_after_rounding(period, factor):
    body = engine.compute(Decimal("15003"), pay_period=period, year=2025).to_dict()
    assert Decimal(body["gross_annual"]) == Decimal("15003") * factor
    deducted = sum(
        Decimal(i["amount_period"]) for i in body["items"] if i["kind"] in ("tax", "social")
    )
    assert Decimal(body["net_period"]) == Decimal(body["gross_period"]) - deducted
    assert (
        next(i["amount_period"] for i in body["items"] if i["kind"] == "net") == body["net_period"]
    )


def test_fortnightly_activation_warehouse_and_posting(client, chart):
    first = client.post(
        "/api/v1/salary/profiles",
        json={
            "label": "Monthly",
            "gross_amount": "32000",
            "pay_period": "monthly",
        },
    ).json()
    second_response = client.post(
        "/api/v1/salary/profiles",
        json={
            "label": "Fortnightly",
            "gross_amount": "15003",
            "pay_period": "fortnightly",
        },
    )
    assert second_response.status_code == 201
    second = second_response.json()
    assert second["breakdown"]["net_period"] == "13307.19"
    assert client.get("/api/v1/analytics/earnings").json()["profile_id"] == second["id"]
    assert client.post(f"/api/v1/salary/profiles/{first['id']}/activate").status_code == 200
    assert client.get("/api/v1/analytics/earnings").json()["profile_id"] == first["id"]
    client.post(f"/api/v1/salary/profiles/{second['id']}/activate")
    profiles = client.get("/api/v1/salary/profiles").json()
    assert [p["id"] for p in profiles if p["is_active"]] == [second["id"]]
    path = f"/api/v1/salary/profiles/{second['id']}/post"
    payload = {"deposit_account_id": chart["1020"].id}
    posted = client.post(path, json=payload).json()
    assert posted["created"] is True
    deposit = next(
        line for line in posted["entry"]["lines"] if line["account_id"] == chart["1020"].id
    )
    assert deposit["debit"] == second["breakdown"]["net_period"]
    assert client.post(path, json=payload).json()["created"] is False


def test_pagination_complete_history_ties_archived_and_voided(client, db_session, chart, user_id):
    # Bulk fixture avoids thousands of HTTP writes; the endpoint still reads real journal rows.
    db_session.execute(
        insert(JournalEntry),
        [
            {
                "id": i,
                "user_id": user_id,
                "occurred_at": datetime(2026, 1, 1),
                "source": EntrySource.MANUAL,
            }
            for i in range(1, 2006)
        ],
    )
    db_session.execute(
        insert(JournalLine),
        [
            line
            for i in range(1, 2006)
            for line in (
                {
                    "entry_id": i,
                    "line_no": 1,
                    "account_id": chart["1020"].id,
                    "debit": Decimal("1"),
                    "credit": Decimal("0"),
                },
                {
                    "entry_id": i,
                    "line_no": 2,
                    "account_id": chart["4010"].id,
                    "debit": Decimal("0"),
                    "credit": Decimal("1"),
                },
            )
        ],
    )
    chart["1020"].archived_at = datetime(2026, 2, 1)
    db_session.commit()
    first = client.get("/api/v1/ledger/entries/page").json()
    assert first["total"] == 2005 and first["posted_total"] == "2005.00"
    assert [i["id"] for i in first["items"]] == list(range(2005, 1995, -1))
    assert first["items"][0]["cash_balance"] == "2005.00"
    second = client.get("/api/v1/ledger/entries/page", params={"page": 2}).json()
    assert second["items"][0]["id"] == 1995
    assert second["items"][0]["cash_balance"] == "1995.00"
    last = client.get("/api/v1/ledger/entries/page", params={"page": 201}).json()
    assert len(last["items"]) == 5
    assert last["items"][-1]["id"] == 1
    assert last["items"][-1]["cash_balance"] == "1.00"
    assert client.get("/api/v1/ledger/entries/page", params={"page": 202}).json()["items"] == []
    # The pre-existing endpoint continues returning an array.
    assert isinstance(client.get("/api/v1/ledger/entries", params={"limit": 1}).json(), list)
    db_session.get(JournalEntry, 1).voided_at = datetime(2026, 2, 1)
    db_session.commit()
    after = client.get("/api/v1/ledger/entries/page").json()
    assert after["total"] == 2004 and after["posted_total"] == "2004.00"
    assert after["items"][0]["cash_balance"] == "2004.00"


def test_empty_and_invalid_pages(client):
    body = client.get("/api/v1/ledger/entries/page").json()
    assert body == {"items": [], "total": 0, "posted_total": "0.00", "page": 1, "page_size": 10}
    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        assert client.get("/api/v1/ledger/entries/page", params=params).status_code == 422
