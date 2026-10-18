"""US-12 (T-12.1): the three OpenAPI stubs exist, answer with their contract and document their errors."""

import pytest
from fastapi.testclient import TestClient

from app.api.control_center.main import app as control_center
from app.api.customer_consumption.main import app as customer_consumption
from app.api.network_inventory.main import app as network_inventory
from app.core.security import issue_token

CUSTOMER = {"Authorization": f"Bearer {issue_token('customer', customer_code='CU-MAC000002')}"}
INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}
MONTH = {"month": "2013-02"}
RANGE = {"start": "2013-03-04T00:00:00Z", "end": "2013-03-04T02:00:00Z"}


@pytest.fixture
def cc():
    return TestClient(customer_consumption)


@pytest.fixture
def ctl():
    return TestClient(control_center)


@pytest.fixture
def inv():
    return TestClient(network_inventory)


# ---------- every API ----------

@pytest.mark.parametrize("app", [customer_consumption, control_center, network_inventory])
def test_health_and_openapi(app):
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"].startswith("VoltiaGrid")
    assert "/health" in spec["paths"]


def test_expected_paths_are_in_the_contracts():
    assert {"/me/consumption/daily", "/customers/{customer_code}/consumption/daily"} <= set(customer_consumption.openapi()["paths"])
    assert {"/transformers/{transformer_code}/load", "/alerts/overload"} <= set(control_center.openapi()["paths"])
    assert {
        "/customers", "/customers/{code}", "/circuits", "/circuits/{code}",
        "/transformers", "/transformers/{code}", "/meters", "/meters/{lclid}",
    } <= set(network_inventory.openapi()["paths"])


# ---------- customer consumption ----------

def test_customer_reads_own_month(cc):
    r = cc.get("/me/consumption/daily", params=MONTH, headers=CUSTOMER)
    assert r.status_code == 200
    body = r.json()
    assert body["customer_code"] == "CU-MAC000002"
    assert len(body["days"]) == 28 * 3
    assert {d["band_name"] for d in body["days"]} == {"peak", "intermediate", "off-peak"}


def test_no_token_or_bad_token_is_401(cc):
    assert cc.get("/me/consumption/daily", params=MONTH).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert cc.get("/me/consumption/daily", params=MONTH, headers=bad).status_code == 401


def test_customer_cannot_read_another_customer(cc):
    r = cc.get("/customers/CU-MAC000999/consumption/daily", params=MONTH, headers=CUSTOMER)
    assert r.status_code == 403


def test_internal_user_reads_any_customer(cc):
    r = cc.get("/customers/CU-MAC000999/consumption/daily", params=MONTH, headers=INTERNAL)
    assert r.status_code == 200


def test_invalid_month_is_422(cc):
    assert cc.get("/me/consumption/daily", params={"month": "2013-13"}, headers=CUSTOMER).status_code == 422


# ---------- control center ----------

def test_transformer_load_per_15_minutes(ctl):
    r = ctl.get("/transformers/TR-00001/load", params=RANGE, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["interval_minutes"] == 15
    assert len(r.json()["points"]) == 8


def test_unknown_transformer_is_404(ctl):
    assert ctl.get("/transformers/TR-99999/load", params=RANGE, headers=INTERNAL).status_code == 404


def test_range_end_before_start_is_422(ctl):
    bad = {"start": RANGE["end"], "end": RANGE["start"]}
    assert ctl.get("/transformers/TR-00001/load", params=bad, headers=INTERNAL).status_code == 422


def test_control_center_is_internal_only(ctl):
    assert ctl.get("/alerts/overload", headers=CUSTOMER).status_code == 403
    assert ctl.get("/alerts/overload", headers=INTERNAL).status_code == 200


# ---------- network inventory ----------

def test_create_customer_201_and_duplicate_409(inv):
    body = {"code": "CU-MAC123456", "acorn_group": "ACORN-E", "acorn_grouped": "Affluent"}
    assert inv.post("/customers", json=body, headers=INTERNAL).status_code == 201
    assert inv.post("/customers", json=body, headers=INTERNAL).status_code == 409


def test_invalid_body_is_422_naming_the_field(inv):
    r = inv.post("/customers", json={"code": "X", "acorn_group": "A", "acorn_grouped": "Rich"}, headers=INTERNAL)
    assert r.status_code == 422
    assert "acorn_grouped" in r.text


def test_unknown_customer_is_404(inv):
    r = inv.get("/customers/CU-MAC000999", headers=INTERNAL)
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_meters_are_paginated_and_filtered(inv):
    r = inv.get("/meters", params={"transformer_code": "TR-00000", "page": 1, "size": 1}, headers=INTERNAL)
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 2 and len(body["items"]) == 1
    assert inv.get("/meters", params={"size": 500}, headers=INTERNAL).status_code == 422


def test_transformer_capacity_can_be_updated(inv):
    r = inv.patch("/transformers/TR-00001", json={"capacity_kva": "160.00"}, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["capacity_kva"] == "160.00"
