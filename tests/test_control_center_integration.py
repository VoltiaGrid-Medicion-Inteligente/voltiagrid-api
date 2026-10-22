from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.control_center.f5_client import F5Client, get_f5_client
from app.api.control_center.main import app
from app.core.db import get_session
from app.core.security import issue_token
from app.models.inventory import Circuit, Transformer
from simulators.common.inventory import Inventory
from simulators.transformer_api.losses import LossStore
from simulators.transformer_api.main import app as f5_app
from simulators.transformer_api.main import get_inventory, get_loss_store, get_seed

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}
START = datetime(2013, 3, 4, 18, 0, tzinfo=timezone.utc)


def window(hours: float = 1, start: datetime = START) -> dict:
    return {"start": start.isoformat(), "end": (start + timedelta(hours=hours)).isoformat()}


@pytest.fixture
def f5():
    inventory = Inventory({"TR-CC001": [f"CC{i:06d}" for i in range(1, 61)],
                           "TR-CC002": [f"CC{i:06d}" for i in range(61, 131)]})
    store = LossStore()
    f5_app.dependency_overrides[get_inventory] = lambda: inventory
    f5_app.dependency_overrides[get_loss_store] = lambda: store
    f5_app.dependency_overrides[get_seed] = lambda: 42
    yield F5Client(TestClient(f5_app))
    f5_app.dependency_overrides.clear()


@pytest.fixture
def client(session, f5):
    circuit = Circuit(code="CT-CC1", capacity_kva=Decimal("1500"))
    session.add_all([
        circuit,
        Transformer(code="TR-CC001", circuit=circuit, capacity_kva=Decimal("141.00")),
        Transformer(code="TR-CC002", circuit=circuit, capacity_kva=Decimal("2.00")),
        Transformer(code="TR-CC003", circuit=circuit, capacity_kva=Decimal("100.00")),
    ])
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_f5_client] = lambda: f5
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_f5_client, None)


# ---------- load ----------

def test_load_matches_f5_and_capacity_from_f4(client, f5):
    body = client.get("/transformers/TR-CC001/load", params=window(2), headers=INTERNAL).json()
    readings = f5.energy("TR-CC001", START, START + timedelta(hours=2))
    assert body["capacity_kva"] == "141.00"
    assert [Decimal(p["load_kw"]) for p in body["points"]] == [(Decimal(str(k)) * 4).quantize(Decimal("0.01")) for _, k in readings]


def test_unknown_transformer_is_404(client):
    r = client.get("/transformers/TR-99999/load", params=window(), headers=INTERNAL)
    assert r.status_code == 404
    assert r.json() == {"detail": "Transformer 'TR-99999' not found"}


def test_transformer_without_meters_in_f5_is_404(client):
    assert client.get("/transformers/TR-CC003/load", params=window(), headers=INTERNAL).status_code == 404


@pytest.mark.parametrize("params,message", [
    ({"start": START.isoformat(), "end": START.isoformat()}, "end must be after start"),
    (window(-1), "end must be after start"),
    (window(24 * 8), "range must be 7 days or less"),
])
def test_empty_or_invalid_ranges_are_422(client, params, message):
    r = client.get("/transformers/TR-CC001/load", params=params, headers=INTERNAL)
    assert r.status_code == 422
    assert r.json()["detail"] == message


def test_dates_without_time_zone_are_422(client):
    r = client.get("/transformers/TR-CC001/load", params={"start": "2013-03-04T18:00:00", "end": "2013-03-04T19:00:00Z"},
                   headers=INTERNAL)
    assert r.status_code == 422


# ---------- alerts ----------

def test_overloaded_transformer_is_flagged_and_others_are_not(client):
    alerts = client.get("/alerts/overload", params={"at": "2013-03-04T19:00:00Z", "circuit_code": "CT-CC1"},
                        headers=INTERNAL).json()
    assert [a["transformer_code"] for a in alerts if a["circuit_code"] == "CT-CC1"] == ["TR-CC002"]
    assert alerts[0]["circuit_code"] == "CT-CC1"


def test_no_alerts_for_an_unknown_circuit(client):
    r = client.get("/alerts/overload", params={"at": "2013-03-04T19:00:00Z", "circuit_code": "CT-NOPE"}, headers=INTERNAL)
    assert r.status_code == 200 and r.json() == []


def test_a_capacity_change_in_f4_changes_the_alerts(client, session):
    session.query(Transformer).filter(Transformer.code == "TR-CC002").update({"capacity_kva": Decimal("400.00")})
    session.flush()
    params = {"at": "2013-03-04T19:00:00Z", "circuit_code": "CT-CC1"}
    assert client.get("/alerts/overload", params=params, headers=INTERNAL).json() == []