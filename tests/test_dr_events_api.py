"""Demand-response events of a customer in the customer API (US-44, T-44.4)."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.customer_consumption.main import app
from app.core.db import get_session
from app.core.security import issue_token
from app.models.demand_response import DrParticipation
from app.models.inventory import Circuit, Customer, Meter, Transformer

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}


def token(code):
    return {"Authorization": f"Bearer {issue_token('customer', customer_code=code)}"}


def participation(code, event_id, day, savings_pct, paid, amount, baseline=Decimal("7.2")):
    return DrParticipation(event_id=event_id, customer_code=code, event_date=day,
                           start_ts=datetime.combine(day, datetime.min.time()).replace(hour=19),
                           end_ts=datetime.combine(day, datetime.min.time()).replace(hour=22),
                           baseline_kwh=baseline, actual_kwh=Decimal("6.0"), savings_kwh=Decimal("1.2"),
                           savings_pct=savings_pct, incentive_paid=paid, incentive_amount=amount)


@pytest.fixture
def client(session):
    circuit = Circuit(code="CT-T01", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-T0001", circuit=circuit, capacity_kva=Decimal("100"))
    one = Customer(code="CU-TEST000001", acorn_group="ACORN-A", acorn_grouped="Affluent")
    two = Customer(code="CU-TEST000002", acorn_group="ACORN-A", acorn_grouped="Affluent")
    session.add_all([circuit, transformer, one, two,
                     Meter(lclid="TEST000001", customer=one, transformer=transformer),
                     Meter(lclid="TEST000002", customer=two, transformer=transformer)])
    session.flush()
    session.add_all([
        participation("CU-TEST000001", "DR-CT-T01-20130722", date(2013, 7, 22), Decimal("0.1667"), True, Decimal("0.36")),
        participation("CU-TEST000001", "DR-CT-T01-20130724", date(2013, 7, 24), Decimal("0.0800"), False, Decimal("0")),
        participation("CU-TEST000001", "DR-CT-T01-20130801", date(2013, 8, 1), Decimal("0.2000"), True, Decimal("0.43")),
        participation("CU-TEST000002", "DR-CT-T01-20130722", date(2013, 7, 22), Decimal("0.1100"), True, Decimal("0.24")),
    ])
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_customer_sees_its_events_of_the_month_with_savings_and_incentive(client):
    r = client.get("/me/events", params={"month": "2013-07"}, headers=token("CU-TEST000001"))
    assert r.status_code == 200
    body = r.json()
    assert [e["event_id"] for e in body["events"]] == ["DR-CT-T01-20130722", "DR-CT-T01-20130724"]
    first = body["events"][0]
    assert (first["start"], first["end"]) == ("2013-07-22T19:00:00", "2013-07-22T22:00:00")
    assert (first["savings_pct"], first["incentive_paid"], first["incentive_amount"]) == ("0.1667", True, "0.36")
    assert body["events"][1]["incentive_paid"] is False
    assert body["incentives_total"] == "0.36"


def test_a_month_without_events_is_an_empty_list(client):
    body = client.get("/me/events", params={"month": "2013-06"}, headers=token("CU-TEST000001")).json()
    assert (body["events"], body["incentives_total"]) == ([], "0.00")


def test_a_customer_cannot_read_another_customers_events(client):
    r = client.get("/customers/CU-TEST000002/events", params={"month": "2013-07"}, headers=token("CU-TEST000001"))
    assert r.status_code == 403


def test_internal_users_read_any_customer(client):
    body = client.get("/customers/CU-TEST000002/events", params={"month": "2013-07"}, headers=INTERNAL).json()
    assert [e["incentive_amount"] for e in body["events"]] == ["0.24"]


def test_internal_token_on_me_is_rejected_and_unknown_customer_is_404(client):
    assert client.get("/me/events", params={"month": "2013-07"}, headers=INTERNAL).status_code == 403
    assert client.get("/customers/CU-NOPE/events", params={"month": "2013-07"}, headers=INTERNAL).status_code == 404


def test_without_token_is_401(client):
    assert client.get("/me/events", params={"month": "2013-07"}).status_code == 401
