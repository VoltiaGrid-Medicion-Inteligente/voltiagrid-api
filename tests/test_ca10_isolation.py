"""CA-10 / RN-11 (US-13, T-13.5): an authenticated customer asking for another customer's
consumption gets 403. End to end: real login, real JWT, real F4 rows in Postgres.

This test replaces the CA-10 xfail of voltiagrid-data (tests/rules/test_acceptance.py).
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.customer_consumption.main import app
from app.core.db import get_session
from app.models.inventory import Circuit, Customer, Meter, Transformer

MONTH = {"month": "2013-02"}


@pytest.fixture
def client(session):
    circuit = Circuit(code="CT-CA10", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-CA10", circuit=circuit, capacity_kva=Decimal("100"))
    alice = Customer(code="CU-CA10ALICE", acorn_group="ACORN-A", acorn_grouped="Affluent")
    bob = Customer(code="CU-CA10BOB", acorn_group="ACORN-P", acorn_grouped="Adversity")
    session.add_all([
        circuit, transformer, alice, bob,
        Meter(lclid="CA10ALICE", customer=alice, transformer=transformer),
        Meter(lclid="CA10BOB", customer=bob, transformer=transformer),
    ])
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/auth/token", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_ca_10_customer_cannot_read_another_customers_consumption(client):
    alice = _login(client, "CU-CA10ALICE", "test-customer-password")
    r = client.get("/customers/CU-CA10BOB/consumption/daily", params=MONTH, headers=alice)
    assert r.status_code == 403
    assert "days" not in r.json()


def test_ca_10_customer_reads_own_consumption(client):
    alice = _login(client, "CU-CA10ALICE", "test-customer-password")
    assert client.get("/customers/CU-CA10ALICE/consumption/daily", params=MONTH, headers=alice).status_code == 200
    assert client.get("/me/consumption/daily", params=MONTH, headers=alice).json()["customer_code"] == "CU-CA10ALICE"


def test_ca_10_authorized_area_reads_any_customer(client):
    internal = _login(client, "internal", "test-internal-password")
    r = client.get("/customers/CU-CA10BOB/consumption/daily", params=MONTH, headers=internal)
    assert r.status_code == 200
    assert r.json()["customer_code"] == "CU-CA10BOB"