"""End-to-end coverage of the HTTP surface."""

from __future__ import annotations

from decimal import Decimal


def test_health_and_meta(client):
    assert client.get("/health").json()["status"] == "ok"
    meta = client.get("/api/v1/meta").json()
    assert meta["currency"] == "PHP"
    assert meta["jurisdiction"] == "PH"


class TestAccounts:
    def test_seeded_chart_is_listed(self, seeded_client):
        accounts = seeded_client.get("/api/v1/accounts").json()
        codes = {a["code"] for a in accounts}
        assert {"1020", "4010", "5030", "6020"} <= codes
        assert all(a["type"] in
                   {"asset", "liability", "equity", "income", "expense"} for a in accounts)

    def test_balances_include_a_type_rollup(self, seeded_client):
        body = seeded_client.get("/api/v1/accounts/balances").json()
        assert body["currency"] == "PHP"
        assert "asset" in body["totals_by_type"]
        assert Decimal(body["net_worth"]) != 0

    def test_create_and_archive(self, seeded_client):
        created = seeded_client.post(
            "/api/v1/accounts",
            json={"code": "5200", "name": "Pet care", "type": "expense"},
        )
        assert created.status_code == 201
        account_id = created.json()["id"]

        assert seeded_client.delete(f"/api/v1/accounts/{account_id}").status_code == 204
        listed = {a["code"] for a in seeded_client.get("/api/v1/accounts").json()}
        assert "5200" not in listed
        with_archived = {
            a["code"]
            for a in seeded_client.get(
                "/api/v1/accounts", params={"include_archived": True}
            ).json()
        }
        assert "5200" in with_archived

    def test_duplicate_code_is_rejected(self, seeded_client):
        payload = {"code": "5210", "name": "First", "type": "expense"}
        assert seeded_client.post("/api/v1/accounts", json=payload).status_code == 201
        assert seeded_client.post("/api/v1/accounts", json=payload).status_code == 409

    def test_a_seeded_account_with_postings_cannot_be_removed(self, seeded_client, chart):
        response = seeded_client.delete(f"/api/v1/accounts/{chart['5010'].id}")
        assert response.status_code == 409
        assert "archived" in response.json()["detail"]

    def test_posting_to_an_archived_account_is_rejected(self, seeded_client, chart):
        created = seeded_client.post(
            "/api/v1/accounts", json={"code": "5220", "name": "Temp", "type": "expense"}
        ).json()
        seeded_client.delete(f"/api/v1/accounts/{created['id']}")

        response = seeded_client.post(
            "/api/v1/ledger/entries/simple",
            json={
                "kind": "expense", "amount": "100.00", "account_id": chart["1010"].id,
                "counter_account_id": created["id"], "occurred_at": "2026-06-10T10:00:00",
            },
        )
        assert response.status_code == 422
        assert "archived" in response.json()["detail"]


class TestLedger:
    def test_entries_carry_their_lines(self, seeded_client):
        entries = seeded_client.get("/api/v1/ledger/entries").json()
        assert entries
        for entry in entries:
            debits = sum(Decimal(line["debit"]) for line in entry["lines"])
            credits = sum(Decimal(line["credit"]) for line in entry["lines"])
            assert debits == credits, entry["id"]

    def test_multi_line_entry_via_the_api(self, seeded_client, chart):
        response = seeded_client.post(
            "/api/v1/ledger/entries",
            json={
                "occurred_at": "2026-06-05T10:00:00",
                "memo": "Split payment",
                "lines": [
                    {"account_id": chart["5030"].id, "debit": "600.00"},
                    {"account_id": chart["5040"].id, "debit": "400.00"},
                    {"account_id": chart["1040"].id, "credit": "1000.00"},
                ],
            },
        )
        assert response.status_code == 201
        assert len(response.json()["lines"]) == 3

    def test_unbalanced_entry_is_rejected_with_422(self, seeded_client, chart):
        response = seeded_client.post(
            "/api/v1/ledger/entries",
            json={
                "occurred_at": "2026-06-05T10:00:00",
                "lines": [
                    {"account_id": chart["5030"].id, "debit": "600.00"},
                    {"account_id": chart["1040"].id, "credit": "500.00"},
                ],
            },
        )
        assert response.status_code == 422
        assert "does not balance" in response.json()["detail"]

    def test_filter_by_account_returns_whole_entries(self, seeded_client, chart):
        entries = seeded_client.get(
            "/api/v1/ledger/entries", params={"account_id": chart["5010"].id}
        ).json()
        assert entries
        for entry in entries:
            assert any(line["account_id"] == chart["5010"].id for line in entry["lines"])
            # The counter-side line comes back too, not just the matched line.
            assert len(entry["lines"]) >= 2

    def test_voided_entries_are_hidden_by_default(self, seeded_client, chart):
        entry = seeded_client.post(
            "/api/v1/ledger/entries/simple",
            json={
                "kind": "expense", "amount": "100.00", "account_id": chart["1010"].id,
                "counter_account_id": chart["5040"].id, "occurred_at": "2026-06-10T10:00:00",
            },
        ).json()
        seeded_client.delete(f"/api/v1/ledger/entries/{entry['id']}")

        visible = {e["id"] for e in seeded_client.get("/api/v1/ledger/entries").json()}
        assert entry["id"] not in visible
        with_voided = {
            e["id"]
            for e in seeded_client.get(
                "/api/v1/ledger/entries", params={"include_voided": True}
            ).json()
        }
        assert entry["id"] in with_voided

    def test_missing_entry_is_404(self, seeded_client):
        assert seeded_client.get("/api/v1/ledger/entries/999999").status_code == 404


class TestSalary:
    def test_calculate_reconciles(self, client):
        body = client.post(
            "/api/v1/salary/calculate", json={"gross_amount": "32000", "pay_period": "monthly"}
        ).json()
        assert Decimal(body["gross_annual"]) - Decimal(body["total_deductions"]) == Decimal(
            body["net_annual"]
        )
        assert body["gross_period"] == "32000.00"

    def test_profile_roundtrip(self, client, chart):
        created = client.post(
            "/api/v1/salary/profiles",
            json={"label": "Test job", "gross_amount": "45000", "pay_period": "monthly"},
        )
        assert created.status_code == 201
        active = client.get("/api/v1/salary/profiles/active").json()
        assert active["label"] == "Test job"


class TestAnalytics:
    def test_overview_shape(self, seeded_client):
        body = seeded_client.get("/api/v1/analytics/overview").json()
        assert body["currency"] == "PHP"
        assert Decimal(body["total_income"]) > 0
        assert Decimal(body["total_expense"]) > 0
        assert body["accounts"]

    def test_monthly_series_is_chronological(self, seeded_client):
        series = seeded_client.get("/api/v1/analytics/monthly", params={"months": 6}).json()[
            "series"
        ]
        assert series == sorted(series, key=lambda p: p["month"])

    def test_monthly_by_account(self, seeded_client):
        body = seeded_client.get("/api/v1/analytics/monthly-by-account").json()
        assert body["months"]
        for s in body["series"]:
            assert len(s["values"]) == len(body["months"])

    def test_running_balance_is_cumulative(self, seeded_client):
        points = seeded_client.get("/api/v1/analytics/running-balance").json()["points"]
        assert points
        running = Decimal("0")
        for point in points:
            running += Decimal(point["net"])
            assert Decimal(point["balance"]) == running

    def test_earnings_waterfall(self, seeded_client):
        body = seeded_client.get("/api/v1/analytics/earnings").json()
        kinds = [i["kind"] for i in body["items"]]
        assert kinds[0] == "gross" and kinds[-1] == "net"
        assert Decimal(body["gross"]) - Decimal(body["total_deductions"]) == Decimal(body["net"])
        assert Decimal("0") < Decimal(body["take_home_rate"]) <= Decimal("1")


class TestDashboard:
    def test_summary_agrees_with_analytics(self, seeded_client):
        params = {"start": "2026-06-01", "end": "2026-06-30"}
        summary = seeded_client.get("/api/v1/dashboard/summary", params=params).json()
        overview = seeded_client.get("/api/v1/analytics/overview", params=params).json()
        assert summary["total_income"] == overview["total_income"]
        assert summary["total_expense"] == overview["total_expense"]
        assert summary["net_cashflow"] == overview["net_cashflow"]

    def test_insights_are_generated(self, seeded_client):
        insights = seeded_client.get("/api/v1/dashboard/summary").json()["insights"]
        assert insights
        assert all(i["severity"] in {"info", "warning", "good"} for i in insights)


class TestBudgets:
    def test_status_matches_the_ledger(self, seeded_client, chart):
        rows = seeded_client.get(
            "/api/v1/budgets/status", params={"scope": "month"}
        ).json()
        assert rows
        for row in rows:
            expected = Decimal(row["limit_amount"]) - Decimal(row["spent"])
            assert Decimal(row["remaining"]) == expected

    def test_budgets_reject_non_expense_accounts(self, seeded_client, chart):
        response = seeded_client.post(
            "/api/v1/budgets",
            json={"account_id": chart["1020"].id, "year": 2026, "month": 6, "limit_amount": "100"},
        )
        assert response.status_code == 422

    def test_fund_override_roundtrip(self, seeded_client):
        default = seeded_client.get("/api/v1/budgets/fund", params={"scope": "month"}).json()
        assert default["is_override"] is False

        seeded_client.post(
            "/api/v1/budgets/fund", json={"scope": "month", "amount": "12345.00"}
        )
        overridden = seeded_client.get("/api/v1/budgets/fund", params={"scope": "month"}).json()
        assert overridden["is_override"] is True
        assert Decimal(overridden["amount"]) == Decimal("12345.00")

        seeded_client.delete("/api/v1/budgets/fund", params={"scope": "month"})
        assert (
            seeded_client.get("/api/v1/budgets/fund", params={"scope": "month"}).json()[
                "is_override"
            ]
            is False
        )


class TestExport:
    def test_ledger_csv_is_line_grained(self, seeded_client):
        response = seeded_client.get("/api/v1/export/ledger.csv")
        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert lines[0].startswith("entry_id,occurred_at,source")
        assert len(lines) > 10

    def test_trial_balance_ties(self, seeded_client):
        response = seeded_client.get("/api/v1/export/trial-balance.csv")
        rows = [r.split(",") for r in response.text.strip().splitlines()]
        total = rows[-1]
        assert total[1] == "TOTAL"
        assert Decimal(total[3]) == Decimal(total[4])


class TestSavingsRate:
    """The reference income must span the same window as the expense.

    An earlier version used the active payslip's net-per-period as the
    reference, so over a multi-month range it compared one month of salary
    against months of spending — producing rates like -326%.
    """

    def test_rate_is_dimensionally_sane_over_every_range(self, seeded_client):
        for params in (
            {},  # all time
            {"start": "2026-06-01", "end": "2026-06-30"},
            {"start": "2026-06-01", "end": "2026-09-30"},
        ):
            body = seeded_client.get("/api/v1/analytics/overview", params=params).json()
            rate = Decimal(body["savings_rate"])
            assert Decimal("-1") <= rate <= Decimal("1"), (params, rate)

    def test_rate_equals_net_over_income(self, seeded_client):
        body = seeded_client.get("/api/v1/analytics/overview").json()
        income = Decimal(body["total_income"])
        expected = ((income - Decimal(body["total_expense"])) / income).quantize(
            Decimal("0.0001")
        )
        assert Decimal(body["savings_rate"]) == expected

    def test_dashboard_agrees(self, seeded_client):
        overview = seeded_client.get("/api/v1/analytics/overview").json()
        summary = seeded_client.get("/api/v1/dashboard/summary").json()
        assert overview["savings_rate"] == summary["savings_rate"]
