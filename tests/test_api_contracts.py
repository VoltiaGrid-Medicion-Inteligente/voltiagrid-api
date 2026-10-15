from fastapi.testclient import TestClient

from app.api.control_center.main import app as control_app
from app.api.customer_consumption.main import app as consumption_app
from app.api.network_inventory.main import app as inventory_app


def test_health_consumption() -> None:
    c = TestClient(consumption_app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_control() -> None:
    c = TestClient(control_app)
    r = c.get("/health")
    assert r.status_code == 200


def test_health_inventory() -> None:
    c = TestClient(inventory_app)
    r = c.get("/health")
    assert r.status_code == 200

def test_me_requires_token() -> None:
    c = TestClient(consumption_app)
    r = c.get("/me/consumption/daily?month=2013-02")
    assert r.status_code == 401


def test_customer_forbidden_other() -> None:
    c = TestClient(consumption_app)
    r = c.get(
        "/customers/MAC000999/consumption/daily?month=2013-02",
        headers={"Authorization": "Bearer stub-customer-MAC000002"},
    )
    assert r.status_code == 403

def test_me_200() -> None:
    c = TestClient(consumption_app)
    r = c.get(
        "/me/consumption/daily?month=2013-02",
        headers={"Authorization": "Bearer stub-customer-MAC000002"},
    )
    assert r.status_code == 200
    assert r.json()["customer_code"] == "MAC000002"


def test_alerts_200_internal() -> None:
    c = TestClient(control_app)
    r = c.get("/alerts/overload", headers={"Authorization": "Bearer stub-internal"})
    assert r.status_code == 200


def test_meters_200_internal() -> None:
    c = TestClient(inventory_app)
    r = c.get(
        "/meters?transformer_code=TR-00001",
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2

def test_alerts_403_customer() -> None:
    c = TestClient(control_app)
    r = c.get(
        "/alerts/overload",
        headers={"Authorization": "Bearer stub-customer-MAC000002"},
    )
    assert r.status_code == 403


def test_meters_403_customer() -> None:
    c = TestClient(inventory_app)
    r = c.get(
        "/meters",
        headers={"Authorization": "Bearer stub-customer-MAC000002"},
    )
    assert r.status_code == 403


def test_get_customer_404() -> None:
    c = TestClient(inventory_app)
    r = c.get(
        "/customers/NOEXISTE",
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 404


def test_create_customer_409() -> None:
    c = TestClient(inventory_app)
    h = {"Authorization": "Bearer stub-internal"}
    body = {"code": "MAC009999", "acorn_group": "ACORN-E", "acorn_grouped": "Affluent"}
    r1 = c.post("/customers", json=body, headers=h)
    assert r1.status_code == 201
    r2 = c.post("/customers", json=body, headers=h)
    assert r2.status_code == 409
    assert r2.json()["code"] == "conflict"

def test_create_customer_201() -> None:
    c = TestClient(inventory_app)
    r = c.post(
        "/customers",
        json={"code": "MAC001010", "acorn_group": "ACORN-E", "acorn_grouped": "Affluent"},
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 201
    assert r.json()["code"] == "MAC001010"


def test_month_422() -> None:
    c = TestClient(consumption_app)
    r = c.get(
        "/me/consumption/daily?month=mal",
        headers={"Authorization": "Bearer stub-customer-MAC000002"},
    )
    assert r.status_code == 422


def test_pagination() -> None:
    c = TestClient(inventory_app)
    r = c.get(
        "/transformers?limit=1&offset=0",
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2
    assert len(r.json()["items"]) == 1


def test_load_200() -> None:
    c = TestClient(control_app)
    r = c.get(
        "/transformers/TR-00001/load",
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 200

def test_get_transformer_404() -> None:
    c = TestClient(inventory_app)
    r = c.get("/transformers/NO", headers={"Authorization": "Bearer stub-internal"})
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"

def test_create_customer_422_invalid_acorn_grouped() -> None:
    c = TestClient(inventory_app)
    r = c.post(
        "/customers",
        json={"code": "MAC007777", "acorn_group": "ACORN-E", "acorn_grouped": "Rico"},
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"

def test_consumption_422_invalid_month() -> None:
    c = TestClient(consumption_app)
    r = c.get(
        "/customers/MAC000002/consumption/daily?month=2013-13",
        headers={"Authorization": "Bearer stub-internal"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"