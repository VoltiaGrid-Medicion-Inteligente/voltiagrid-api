"""US-18 (T-18.3): every error of the APIs follows one JSON format."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.network_inventory.main import app as inventory
from app.core.db import get_session
from app.core.errors import ConflictError, NotFoundError, register_error_handlers
from app.core.security import issue_token

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}


def _demo_app() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/missing")
    def missing():
        raise NotFoundError("Transformer", "TR-99999")

    @app.get("/duplicate")
    def duplicate():
        raise ConflictError("Customer", "CU-MAC000002")

    @app.get("/boom")
    def boom():
        raise RuntimeError("database password is xyz")

    @app.get("/typed")
    def typed(size: int):
        return {"size": size}

    return TestClient(app, raise_server_exceptions=False)


def test_not_found_and_conflict_have_a_clear_detail():
    client = _demo_app()
    assert client.get("/missing").json() == {"detail": "Transformer 'TR-99999' not found"}
    assert client.get("/missing").status_code == 404
    assert client.get("/duplicate").json() == {"detail": "Customer 'CU-MAC000002' already exists"}
    assert client.get("/duplicate").status_code == 409


def test_validation_error_names_each_field():
    r = _demo_app().get("/typed", params={"size": "big"})
    assert r.status_code == 422
    body = r.json()
    assert body["detail"] == "Validation error"
    assert [e["field"] for e in body["errors"]] == ["size"]


def test_unexpected_error_is_500_without_internal_details():
    r = _demo_app().get("/boom")
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}


@pytest.fixture
def inventory_client():
    # These errors happen before any query, so no database is needed.
    inventory.dependency_overrides[get_session] = lambda: None
    yield TestClient(inventory)
    inventory.dependency_overrides.pop(get_session, None)


def test_inventory_body_errors_use_the_same_format(inventory_client):
    client = inventory_client
    r = client.post("/circuits", json={"code": "CT-001", "capacity_kva": "-5"}, headers=INTERNAL)
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "capacity_kva"


def test_auth_errors_use_the_same_format(inventory_client):
    r = inventory_client.get("/meters")
    assert r.status_code == 401
    assert r.json() == {"detail": "Missing bearer token"}
