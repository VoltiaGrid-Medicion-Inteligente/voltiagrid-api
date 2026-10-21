"""US-18 (T-18.4): integration tests of the network inventory API against Postgres.

Every test runs inside a transaction that is rolled back, so the database is
left as it was (the seed data, if any, is not touched).
"""

import pytest
from fastapi.testclient import TestClient

from app.api.network_inventory.main import app
from app.core.db import get_session
from app.core.security import issue_token

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}
CUSTOMER = {"Authorization": f"Bearer {issue_token('customer', customer_code='CU-MAC000002')}"}


@pytest.fixture
def api(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def network(api):
    """CT-IT1 -> TR-IT001 (3 meters) and TR-IT002 (no meters); 3 customers."""
    def post(path, body):
        r = api.post(path, json=body, headers=INTERNAL)
        assert r.status_code == 201, r.text
        return r.json()

    post("/circuits", {"code": "CT-IT1", "capacity_kva": "1500.00"})
    post("/transformers", {"code": "TR-IT001", "circuit_code": "CT-IT1", "capacity_kva": "150.00"})
    post("/transformers", {"code": "TR-IT002", "circuit_code": "CT-IT1", "capacity_kva": "300.00"})
    for i in range(1, 4):
        post("/customers", {"code": f"CU-IT{i:04d}", "acorn_group": "ACORN-A", "acorn_grouped": "Affluent"})
        post("/meters", {"lclid": f"IT{i:04d}", "customer_code": f"CU-IT{i:04d}", "transformer_code": "TR-IT001"})
    return api


# ---------- create ----------

def test_create_returns_201_and_the_record_is_saved(network):
    r = network.get("/customers/CU-IT0001", headers=INTERNAL)
    assert r.status_code == 200
    assert r.json() == {"code": "CU-IT0001", "acorn_group": "ACORN-A", "acorn_grouped": "Affluent"}


def test_counts_follow_the_relationships(network):
    assert network.get("/circuits/CT-IT1", headers=INTERNAL).json()["transformers"] == 2
    assert network.get("/transformers/TR-IT001", headers=INTERNAL).json()["meters"] == 3
    assert network.get("/transformers/TR-IT002", headers=INTERNAL).json()["meters"] == 0


def test_duplicate_natural_key_is_409(network):
    r = network.post("/meters", json={"lclid": "IT0001", "customer_code": "CU-IT0001", "transformer_code": "TR-IT002"},
                     headers=INTERNAL)
    assert r.status_code == 409
    assert r.json()["detail"] == "Meter 'IT0001' already exists"


def test_create_with_unknown_reference_is_404(network):
    r = network.post("/transformers", json={"code": "TR-IT003", "circuit_code": "CT-NOPE", "capacity_kva": "100"},
                     headers=INTERNAL)
    assert r.status_code == 404
    assert r.json()["detail"] == "Circuit 'CT-NOPE' not found"


# ---------- get / not found ----------

@pytest.mark.parametrize("path,message", [
    ("/customers/CU-NOPE", "Customer 'CU-NOPE' not found"),
    ("/circuits/CT-NOPE", "Circuit 'CT-NOPE' not found"),
    ("/transformers/TR-NOPE", "Transformer 'TR-NOPE' not found"),
    ("/meters/NOPE", "Meter 'NOPE' not found"),
])
def test_unknown_identifier_is_404_with_a_clear_message(api, path, message):
    r = api.get(path, headers=INTERNAL)
    assert r.status_code == 404
    assert r.json() == {"detail": message}


# ---------- validation ----------

@pytest.mark.parametrize("path,body,field", [
    ("/customers", {"code": "CU-IT9", "acorn_group": "ACORN-A", "acorn_grouped": "Rich"}, "acorn_grouped"),
    ("/customers", {"code": "IT9", "acorn_group": "ACORN-A", "acorn_grouped": "Affluent"}, "code"),
    ("/circuits", {"code": "CT-IT9", "capacity_kva": "0"}, "capacity_kva"),
    ("/transformers", {"code": "TR-IT9", "circuit_code": "CT-IT1"}, "capacity_kva"),
    ("/meters", {"lclid": "it-9", "customer_code": "CU-IT0001", "transformer_code": "TR-IT001"}, "lclid"),
])
def test_invalid_body_is_422_naming_the_field(network, path, body, field):
    r = network.post(path, json=body, headers=INTERNAL)
    assert r.status_code == 422
    assert r.json()["detail"] == "Validation error"
    assert field in [e["field"] for e in r.json()["errors"]]


def test_invalid_capacity_update_is_422(network):
    r = network.patch("/transformers/TR-IT001", json={"capacity_kva": "-1"}, headers=INTERNAL)
    assert r.status_code == 422


def test_capacity_update_is_saved(network):
    assert network.patch("/circuits/CT-IT1", json={"capacity_kva": "1750.25"}, headers=INTERNAL).status_code == 200
    assert network.get("/circuits/CT-IT1", headers=INTERNAL).json()["capacity_kva"] == "1750.25"


# ---------- pagination and filters ----------

def test_returns_only_the_requested_page(network):
    first = network.get("/meters", params={"transformer_code": "TR-IT001", "page": 1, "size": 2}, headers=INTERNAL).json()
    second = network.get("/meters", params={"transformer_code": "TR-IT001", "page": 2, "size": 2}, headers=INTERNAL).json()
    assert first["total"] == second["total"] == 3
    assert [m["lclid"] for m in first["items"]] == ["IT0001", "IT0002"]
    assert [m["lclid"] for m in second["items"]] == ["IT0003"]


def test_page_past_the_end_is_empty(network):
    r = network.get("/meters", params={"transformer_code": "TR-IT001", "page": 5, "size": 2}, headers=INTERNAL).json()
    assert r["items"] == [] and r["total"] == 3


@pytest.mark.parametrize("params", [{"size": 0}, {"size": 201}, {"page": 0}])
def test_page_parameters_out_of_range_are_422(api, params):
    assert api.get("/meters", params=params, headers=INTERNAL).status_code == 422


def test_filters_combine(network):
    r = network.get("/meters", params={"transformer_code": "TR-IT001", "customer_code": "CU-IT0002"}, headers=INTERNAL)
    assert [m["lclid"] for m in r.json()["items"]] == ["IT0002"]
    r = network.get("/transformers", params={"circuit_code": "CT-IT1"}, headers=INTERNAL)
    assert r.json()["total"] == 2


# ---------- access ----------

def test_customers_cannot_use_the_inventory(api):
    assert api.get("/meters", headers=CUSTOMER).status_code == 403
