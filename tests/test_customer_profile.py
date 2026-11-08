"""KAN-349 (US-69, T-69.2): GET /me/profile returns the contract, socioeconomic group, meter, transformer and circuit
of the authenticated customer. Internal users get 403 and use the inventory API."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.customer_consumption.main import app
from app.core.db import get_session
from app.core.security import issue_token
from app.models.inventory import Circuit, Contract, Customer, Meter, Transformer

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}


@pytest.fixture
def client_with_profile(session):
    """A customer with one meter, one transformer, one circuit and two contracts (the newer one counts)."""
    circuit = Circuit(code="CT-PROF01", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-PROF01", circuit=circuit, capacity_kva=Decimal("100"))
    customer = Customer(code="CU-PROFTEST01", acorn_group="ACORN-A", acorn_grouped="Affluent")
    import datetime as dt

    session.add_all([
        circuit,
        transformer,
        customer,
        Meter(lclid="PROF000001", customer=customer, transformer=transformer),
        Contract(code="CO-PROF-OLD", customer=customer, tariff_type="standard",
                 start_date=dt.date(2012, 1, 1), end_date=dt.date(2013, 1, 1)),
        Contract(code="CO-PROF-NEW", customer=customer, tariff_type="dynamic", start_date=dt.date(2013, 1, 1)),
    ])
    session.flush()

    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_customer_reads_own_profile(client_with_profile):
    token = {"Authorization": f"Bearer {issue_token('customer', customer_code='CU-PROFTEST01')}"}
    r = client_with_profile.get("/me/profile", headers=token)
    assert r.status_code == 200
    assert r.json() == {
        "customer_code": "CU-PROFTEST01",
        "tariff_type": "dynamic",
        "socioeconomic_group": "Affluent",
        "meters": [{
            "lclid": "PROF000001",
            "transformer": {"code": "TR-PROF01", "capacity_kva": "100.00"},
            "circuit": {"code": "CT-PROF01"},
        }],
    }


def test_internal_user_gets_403_on_me_profile(client_with_profile):
    r = client_with_profile.get("/me/profile", headers=INTERNAL)
    assert r.status_code == 403
    assert "inventory API" in r.json()["detail"]


def test_no_token_is_401(client_with_profile):
    assert client_with_profile.get("/me/profile").status_code == 401


def test_customer_without_contract_has_null_tariff(session):
    circuit = Circuit(code="CT-PROF02", capacity_kva=Decimal("1000"))
    transformer = Transformer(code="TR-PROF02", circuit=circuit, capacity_kva=Decimal("50"))
    customer = Customer(code="CU-PROFTEST02", acorn_group="ACORN-B", acorn_grouped="Unknown")
    session.add_all([circuit, transformer, customer])
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    try:
        token = {"Authorization": f"Bearer {issue_token('customer', customer_code='CU-PROFTEST02')}"}
        body = TestClient(app).get("/me/profile", headers=token).json()
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert body["tariff_type"] is None
    assert body["meters"] == []
