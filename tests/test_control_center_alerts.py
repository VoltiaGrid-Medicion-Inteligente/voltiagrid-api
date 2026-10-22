"""US-19 (T-19.2): a transformer above its capacity appears as an active overload alert."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.control_center.service import interval_containing
from app.core.security import issue_token

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}
AT = "2013-03-04T19:07:00Z"


@pytest.fixture
def client(control_center_app):
    return TestClient(control_center_app)


def test_overloaded_test_transformer_is_flagged(client):
    r = client.get("/alerts/overload", params={"at": AT}, headers=INTERNAL)
    assert r.status_code == 200
    alerts = r.json()
    assert [a["transformer_code"] for a in alerts] == ["TR-00002"]
    alert = alerts[0]
    assert Decimal(alert["capacity_pct"]) > 100
    assert alert["circuit_code"] == "CT-000"
    assert alert["capacity_kva"] == "2.00"


def test_alert_interval_is_the_15_minutes_that_contain_at(client):
    alert = client.get("/alerts/overload", params={"at": AT}, headers=INTERNAL).json()[0]
    assert datetime.fromisoformat(alert["interval_start"]) == datetime(2013, 3, 4, 19, 0, tzinfo=timezone.utc)


def test_transformer_below_capacity_is_not_flagged(client):
    codes = [a["transformer_code"] for a in client.get("/alerts/overload", params={"at": AT}, headers=INTERNAL).json()]
    assert "TR-00001" not in codes


def test_filter_by_circuit(client):
    assert client.get("/alerts/overload", params={"at": AT, "circuit_code": "CT-999"}, headers=INTERNAL).json() == []


def test_interval_containing():
    assert interval_containing(datetime(2013, 1, 1, 10, 44, 59)) == datetime(2013, 1, 1, 10, 30)
