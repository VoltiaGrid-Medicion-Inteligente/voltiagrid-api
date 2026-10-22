"""US-19 (T-19.1): the load of a transformer per 15-minute interval matches F5, with % of capacity."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.control_center.f5_client import F5Client, get_f5_client
from app.core.security import issue_token

INTERNAL = {"Authorization": f"Bearer {issue_token('internal')}"}
START = datetime(2013, 3, 4, 17, 0, tzinfo=timezone.utc)
RANGE = {"start": START.isoformat(), "end": (START + timedelta(hours=3)).isoformat()}


@pytest.fixture
def client(control_center_app):
    return TestClient(control_center_app)


def test_values_match_f5_for_a_test_transformer(client, f5_test_client):
    r = client.get("/transformers/TR-00001/load", params=RANGE, headers=INTERNAL)
    assert r.status_code == 200
    body = r.json()
    f5 = f5_test_client.energy("TR-00001", START, START + timedelta(hours=3))
    assert len(body["points"]) == len(f5) == 12
    for point, (ts, kwh) in zip(body["points"], f5):
        assert datetime.fromisoformat(point["interval_start"]) == ts
        load_kw = Decimal(str(kwh)) * 4
        assert Decimal(point["load_kw"]) == load_kw.quantize(Decimal("0.01"))
        assert Decimal(point["capacity_pct"]) == (load_kw / Decimal("141.00") * 100).quantize(Decimal("0.1"))


def test_capacity_comes_from_f4(client):
    assert client.get("/transformers/TR-00002/load", params=RANGE, headers=INTERNAL).json()["capacity_kva"] == "2.00"


def test_f5_down_is_502(control_center_app):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    down = F5Client(httpx.Client(base_url="http://f5", transport=httpx.MockTransport(refuse)))
    control_center_app.dependency_overrides[get_f5_client] = lambda: down
    r = TestClient(control_center_app).get("/transformers/TR-00001/load", params=RANGE, headers=INTERNAL)
    assert r.status_code == 502
    assert r.json() == {"detail": "F5 transformer metering API is not available"}
