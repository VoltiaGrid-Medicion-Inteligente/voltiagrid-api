"""US-13 (T-13.2): the daily consumption endpoint returns what the meters of the customer consumed."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.customer_consumption.main import app
from app.api.customer_consumption.service import daily_by_band, is_missing_day
from app.core.db import get_session
from app.core.security import issue_token
from app.core.tariffs import TariffCalendar
from app.models.inventory import Circuit, Customer, Meter, Transformer
from simulators.common.consumption import half_hour_kwh

TARIFFS = TariffCalendar.from_csv("data/reference/tariffs.csv")
INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}
SEED = 42


# ---------- service (no database) ----------

def test_rows_match_the_consumption_model_for_one_meter():
    rows = daily_by_band(["MAC000002"], "2013-02", TARIFFS, SEED, defect_rate=0)
    assert len(rows) == 28 * 3

    day_start = datetime(2013, 2, 10, tzinfo=timezone.utc)
    expected = {"off-peak": 0.0, "intermediate": 0.0, "peak": 0.0}
    for i in range(48):
        ts = day_start + i * timedelta(minutes=30)
        expected[TARIFFS.band_for(ts).band_name] += half_hour_kwh("MAC000002", ts, SEED)
    day_rows = {r["band_name"]: r for r in rows if r["date"] == day_start.date()}
    for band, kwh in expected.items():
        assert day_rows[band]["energy_kwh"] == Decimal(str(kwh)).quantize(Decimal("0.001"))
    assert [day_rows[b]["readings"] for b in ("off-peak", "intermediate", "peak")] == [20, 20, 8]


def test_cost_is_energy_times_band_price():
    rows = daily_by_band(["MAC000002"], "2013-02", TARIFFS, SEED, defect_rate=0)
    peak = next(r for r in rows if r["band_name"] == "peak")
    assert abs(peak["cost"] - peak["energy_kwh"] * Decimal("0.30")) < Decimal("0.001")


def test_two_meters_add_up():
    one = daily_by_band(["MAC000002"], "2013-02", TARIFFS, SEED, defect_rate=0)
    two = daily_by_band(["MAC000002", "MAC000003"], "2013-02", TARIFFS, SEED, defect_rate=0)
    other = daily_by_band(["MAC000003"], "2013-02", TARIFFS, SEED, defect_rate=0)
    assert abs(two[0]["energy_kwh"] - one[0]["energy_kwh"] - other[0]["energy_kwh"]) <= Decimal("0.002")


def test_silent_days_in_f3_are_estimated():
    none = daily_by_band(["MAC000002"], "2013-02", TARIFFS, SEED, defect_rate=0)
    every = daily_by_band(["MAC000002"], "2013-02", TARIFFS, SEED, defect_rate=1)
    assert all(r["estimated_readings"] == 0 for r in none)
    assert all(r["estimated_readings"] == r["readings"] for r in every)


def test_missing_day_rule_is_reproducible():
    day = datetime(2013, 2, 10).date()
    assert is_missing_day("MAC000002", day, SEED, 0.5) == is_missing_day("MAC000002", day, SEED, 0.5)


def test_customer_without_meters_has_no_rows():
    assert daily_by_band([], "2013-02", TARIFFS, SEED, defect_rate=0) == []


# ---------- endpoint against Postgres ----------

@pytest.fixture
def client_with_customer(session):
    """A customer with one meter inside a transaction that is rolled back after the test."""
    circuit = Circuit(code="CT-T01", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-T0001", circuit=circuit, capacity_kva=Decimal("100"))
    customer = Customer(code="CU-TEST000001", acorn_group="ACORN-A", acorn_grouped="Affluent")
    session.add_all([circuit, transformer, customer, Meter(lclid="TEST000001", customer=customer, transformer=transformer)])
    session.flush()

    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_endpoint_matches_the_meter_of_the_customer(client_with_customer):
    r = client_with_customer.get("/customers/CU-TEST000001/consumption/daily", params={"month": "2013-02"}, headers=INTERNAL)
    assert r.status_code == 200
    body = r.json()
    expected = daily_by_band(["TEST000001"], "2013-02", TARIFFS, SEED, defect_rate=0.02)
    assert len(body["days"]) == len(expected) == 28 * 3
    assert [Decimal(d["energy_kwh"]) for d in body["days"]] == [e["energy_kwh"] for e in expected]


def test_customer_reads_own_month_with_token(client_with_customer):
    token = {"Authorization": f"Bearer {issue_token('customer', customer_code='CU-TEST000001')}"}
    r = client_with_customer.get("/me/consumption/daily", params={"month": "2013-02"}, headers=token)
    assert r.status_code == 200
    assert r.json()["customer_code"] == "CU-TEST000001"


def test_unknown_customer_is_404(client_with_customer):
    r = client_with_customer.get("/customers/CU-NOPE/consumption/daily", params={"month": "2013-02"}, headers=INTERNAL)
    assert r.status_code == 404
    assert r.json()["detail"] == "Customer 'CU-NOPE' not found"
