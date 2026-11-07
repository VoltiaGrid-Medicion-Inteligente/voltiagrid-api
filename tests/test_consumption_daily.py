"""Precomputed daily consumption for the customer API (US-47, T-47.2)."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.customer_consumption.main import app
from app.api.customer_consumption.service import daily_by_band
from app.core.db import get_session
from app.core.security import issue_token
from app.core.tariffs import TariffCalendar
from app.models.consumption import ConsumptionDaily
from app.models.inventory import Circuit, Customer, Meter, Transformer
from scripts.build_consumption_daily import build, months_between

TARIFFS = TariffCalendar.from_csv("data/reference/tariffs.csv")
INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}


def test_month_range_crosses_the_year():
    assert months_between("2012-11", "2013-02") == ["2012-11", "2012-12", "2013-01", "2013-02"]


@pytest.fixture
def customer(session):
    circuit = Circuit(code="CT-T01", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-T0001", circuit=circuit, capacity_kva=Decimal("100"))
    customer = Customer(code="CU-TEST000001", acorn_group="ACORN-A", acorn_grouped="Affluent")
    session.add_all([circuit, transformer, customer,
                     Meter(lclid="TEST000001", customer=customer, transformer=transformer),
                     Meter(lclid="TEST000002", customer=customer, transformer=transformer)])
    session.flush()
    session.commit = session.flush          # build() commits per month; inside the test transaction, flush instead
    app.dependency_overrides[get_session] = lambda: session
    yield session
    app.dependency_overrides.pop(get_session, None)


def test_build_stores_what_the_api_computes(customer):
    written = build(customer, ["2013-02"], TARIFFS, 42, 0.02)
    expected = daily_by_band(["TEST000001", "TEST000002"], "2013-02", TARIFFS, 42, 0.02)
    stored = customer.scalar(select(func.count()).select_from(ConsumptionDaily)
                             .where(ConsumptionDaily.customer_code == "CU-TEST000001"))
    assert stored == len(expected) == 28 * 3
    assert written >= stored                # plus the customers the database already had


def test_api_answers_from_the_table_with_the_same_body(customer):
    client = TestClient(app)
    params = {"month": "2013-02"}
    computed = client.get("/customers/CU-TEST000001/consumption/daily", params=params, headers=INTERNAL).json()
    build(customer, ["2013-02"], TARIFFS, 42, 0.02)
    stored = client.get("/customers/CU-TEST000001/consumption/daily", params=params, headers=INTERNAL).json()
    assert stored == computed


def test_api_reads_the_table_when_the_month_is_built(customer):
    build(customer, ["2013-02"], TARIFFS, 42, 0.02)
    row = customer.scalar(select(ConsumptionDaily).where(ConsumptionDaily.customer_code == "CU-TEST000001")
                          .order_by(ConsumptionDaily.date).limit(1))
    row.energy_kwh = Decimal("999.000")     # a marker only the table has
    customer.flush()
    token = {"Authorization": f"Bearer {issue_token('customer', customer_code='CU-TEST000001')}"}
    body = TestClient(app).get("/me/consumption/daily", params={"month": "2013-02"}, headers=token).json()
    assert "999.000" in {d["energy_kwh"] for d in body["days"]}


def test_a_month_not_built_is_still_computed(customer):
    build(customer, ["2013-02"], TARIFFS, 42, 0.02)
    body = TestClient(app).get("/customers/CU-TEST000001/consumption/daily", params={"month": "2013-03"},
                               headers=INTERNAL).json()
    assert len(body["days"]) == 31 * 3
