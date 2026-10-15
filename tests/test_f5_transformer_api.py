"""US-15 (T-15.1): F5 delivers energy every 15 minutes equal to the sum of the transformer's meters."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from seed.defects import DefectCatalog
from simulators.common.consumption import half_hour_kwh, quarter_hour_kwh
from simulators.common.inventory import Inventory
from simulators.concentrator.generator import ConcentratorSimulator
from simulators.transformer_api.main import app, get_inventory, get_seed

START = datetime(2013, 1, 1, tzinfo=UTC)
INVENTORY = Inventory({
    "TR-00001": [f"MAC{i:06d}" for i in range(1, 61)],
    "TR-00002": [f"MAC{i:06d}" for i in range(61, 131)],
})


@pytest.fixture
def client():
    app.dependency_overrides[get_inventory] = lambda: INVENTORY
    app.dependency_overrides[get_seed] = lambda: 42
    yield TestClient(app)
    app.dependency_overrides.clear()


def energy(client, code="TR-00001", start=START, hours=1):
    r = client.get(f"/transformers/{code}/energy",
                   params={"start": start.isoformat(), "end": (start + timedelta(hours=hours)).isoformat()})
    assert r.status_code == 200, r.text
    return r.json()["readings"]


def metered(code, ts):
    return sum(quarter_hour_kwh(m, ts, 42) for m in INVENTORY.meters_of(code))


def test_readings_every_15_minutes(client):
    rows = energy(client, hours=2)
    assert len(rows) == 8
    minutes = [datetime.fromisoformat(r["interval_start"]).minute for r in rows]
    assert minutes == [0, 15, 30, 45] * 2


def test_without_losses_delivered_equals_sum_of_meters(client):
    for row in energy(client, hours=24):
        ts = datetime.fromisoformat(row["interval_start"])
        assert row["delivered_kwh"] == pytest.approx(metered("TR-00001", ts), abs=1e-3)


def test_f5_matches_what_f3_sends_for_the_same_meters(client):
    sim = ConcentratorSimulator(inventory=INVENTORY, catalog=DefectCatalog(base_rate=0.0), gap_rate=0.0)
    f3 = sim.tick(START)[0].message
    f3_total = sum(r["energy_kwh"] for r in f3["readings"])
    f5_total = sum(r["delivered_kwh"] for r in energy(client, hours=0.5))
    assert f5_total == pytest.approx(f3_total, abs=1e-2)
    assert f3_total == pytest.approx(sum(half_hour_kwh(m, START, 42) for m in INVENTORY.meters_of("TR-00001")))


def test_unknown_transformer_returns_404(client):
    r = client.get("/transformers/TR-99999/energy", params={"start": "2013-01-01T00:00:00Z", "end": "2013-01-01T01:00:00Z"})
    assert r.status_code == 404


def test_range_over_7_days_returns_422(client):
    r = client.get("/transformers/TR-00001/energy", params={"start": "2013-01-01T00:00:00Z", "end": "2013-01-09T00:00:00Z"})
    assert r.status_code == 422


def test_dates_without_time_zone_return_422(client):
    r = client.get("/transformers/TR-00001/energy", params={"start": "2013-01-01T00:00:00", "end": "2013-01-01T01:00:00Z"})
    assert r.status_code == 422


def test_list_transformers(client):
    assert client.get("/transformers").json() == [
        {"transformer_code": "TR-00001", "meters": 60},
        {"transformer_code": "TR-00002", "meters": 70},
    ]
