"""KAN-350 (US-69, T-69.3): GET /me/consumption/intervals returns the 48 half hours of one day of the authenticated
customer, and the API allows the portal origin only (CORS from config, never '*')."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.customer_consumption.main import app
from app.api.customer_consumption.service import _meter_readings, daily_by_band
from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import issue_token
from app.core.tariffs import TariffCalendar
from app.models.inventory import Circuit, Customer, Meter, Transformer

TARIFFS = TariffCalendar.from_csv(get_settings().tariffs_csv)
SETTINGS = get_settings()
DAY = date(2013, 3, 1)
INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}


def _customer_token(code):
    return {"Authorization": f"Bearer {issue_token('customer', customer_code=code)}"}


@pytest.fixture
def client(session):
    """Two customers with one meter each, inside a transaction rolled back after the test."""
    circuit = Circuit(code="CT-INT01", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-INT01", circuit=circuit, capacity_kva=Decimal("100"))
    alice = Customer(code="CU-INTALICE", acorn_group="ACORN-A", acorn_grouped="Affluent")
    bob = Customer(code="CU-INTBOB", acorn_group="ACORN-B", acorn_grouped="Adversity")
    no_meters = Customer(code="CU-INTNONE", acorn_group="ACORN-C", acorn_grouped="Unknown")
    session.add_all([circuit, transformer, alice, bob, no_meters,
                     Meter(lclid="INTALICE01", customer=alice, transformer=transformer),
                     Meter(lclid="INTBOB001", customer=bob, transformer=transformer)])
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_full_day_has_48_intervals_in_order(client):
    r = client.get("/me/consumption/intervals", params={"date": DAY.isoformat()}, headers=_customer_token("CU-INTALICE"))
    assert r.status_code == 200
    body = r.json()
    assert body["customer_code"] == "CU-INTALICE" and body["date"] == DAY.isoformat()
    starts = [datetime.fromisoformat(i["start"].replace("Z", "+00:00")) for i in body["intervals"]]
    assert len(starts) == 48
    assert starts == sorted(starts)
    assert starts[0] == datetime(2013, 3, 1, tzinfo=timezone.utc)
    assert starts[-1] == datetime(2013, 3, 1, 23, 30, tzinfo=timezone.utc)


def test_intervals_add_up_to_the_daily_total(client):
    token = _customer_token("CU-INTALICE")
    intervals = client.get("/me/consumption/intervals", params={"date": DAY.isoformat()}, headers=token).json()
    total = sum(Decimal(i["energy_kwh"]) for i in intervals["intervals"])
    daily = daily_by_band(["INTALICE01"], "2013-03", TARIFFS, SETTINGS.model_seed, SETTINGS.defect_rate)
    expected = sum(r["energy_kwh"] for r in daily if r["date"] == DAY)
    assert abs(total - expected) <= Decimal("0.05")  # 48 values rounded to 3 decimals each


def test_bands_and_estimated_flags_match_the_model(client):
    body = client.get("/me/consumption/intervals", params={"date": DAY.isoformat()},
                      headers=_customer_token("CU-INTALICE")).json()
    readings = _meter_readings("INTALICE01", datetime(2013, 3, 1, tzinfo=timezone.utc),
                               datetime(2013, 3, 2, tzinfo=timezone.utc), SETTINGS.model_seed, SETTINGS.defect_rate)
    for item, reading in zip(body["intervals"], readings):
        assert item["band_name"] == TARIFFS.band_for(reading.interval_start).band_name
        assert item["estimated"] is reading.estimated


def test_customer_without_meters_gets_404(client):
    r = client.get("/me/consumption/intervals", params={"date": DAY.isoformat()}, headers=_customer_token("CU-INTNONE"))
    assert r.status_code == 404


def test_customer_only_sees_their_own_meter(client):
    body = client.get("/me/consumption/intervals", params={"date": DAY.isoformat()},
                      headers=_customer_token("CU-INTBOB")).json()
    assert body["customer_code"] == "CU-INTBOB"
    assert "CU-INTALICE" not in str(body)


def test_internal_user_gets_403(client):
    assert client.get("/me/consumption/intervals", params={"date": DAY.isoformat()}, headers=INTERNAL).status_code == 403


def test_no_token_is_401(client):
    assert client.get("/me/consumption/intervals", params={"date": DAY.isoformat()}).status_code == 401


def test_bad_date_is_422(client):
    r = client.get("/me/consumption/intervals", params={"date": "2013-02-30"}, headers=_customer_token("CU-INTALICE"))
    assert r.status_code == 422


def test_cors_allows_the_portal_origin_only(client):
    ok = client.options("/me/consumption/intervals", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    other = client.options("/me/consumption/intervals", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert other.headers.get("access-control-allow-origin") is None
