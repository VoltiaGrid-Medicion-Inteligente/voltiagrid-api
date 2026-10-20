"""US-15 (T-15.3), CA-05 input: with a 15% loss injected in a period, the energy F5 delivers is
15% higher than what the transformer's meters recorded in that period, and only there."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from simulators.common.consumption import quarter_hour_kwh
from simulators.common.inventory import Inventory
from simulators.transformer_api.losses import LossStore
from simulators.transformer_api.main import app, get_inventory, get_loss_store, get_seed

SEED = 42
START = datetime(2013, 3, 4, tzinfo=timezone.utc)          # Monday
LOSS_START, LOSS_END = START + timedelta(days=1), START + timedelta(days=4)   # 3 days, as RN-06 needs
INVENTORY = Inventory({"TR-00001": [f"MAC{i:06d}" for i in range(1, 65)]})


@pytest.fixture
def client():
    store = LossStore()
    app.dependency_overrides[get_inventory] = lambda: INVENTORY
    app.dependency_overrides[get_loss_store] = lambda: store
    app.dependency_overrides[get_seed] = lambda: SEED
    yield TestClient(app)
    app.dependency_overrides.clear()


def metered(ts: datetime) -> float:
    return sum(quarter_hour_kwh(m, ts, SEED) for m in INVENTORY.meters_of("TR-00001"))


def test_15_percent_loss_makes_delivered_15_percent_higher_only_in_its_period(client):
    r = client.post("/losses", json={"transformer_code": "TR-00001", "start": LOSS_START.isoformat(),
                                    "end": LOSS_END.isoformat(), "loss_pct": 0.15})
    assert r.status_code == 201

    r = client.get("/transformers/TR-00001/energy",
                params={"start": START.isoformat(), "end": (START + timedelta(days=5)).isoformat()})
    assert r.status_code == 200
    rows = r.json()["readings"]
    assert len(rows) == 5 * 96

    inside = outside = 0
    for row in rows:
        ts = datetime.fromisoformat(row["interval_start"])
        meters = metered(ts)
        if LOSS_START <= ts < LOSS_END:
            inside += 1
            assert (row["delivered_kwh"] - meters) / meters == pytest.approx(0.15, abs=1e-3)
        else:
            outside += 1
            assert row["delivered_kwh"] == pytest.approx(meters, abs=1e-3)
    assert (inside, outside) == (3 * 96, 2 * 96)


def test_daily_loss_is_15_percent_on_each_of_the_3_days(client):
    client.post("/losses", json={"transformer_code": "TR-00001", "start": LOSS_START.isoformat(),
                                "end": LOSS_END.isoformat(), "loss_pct": 0.15})
    for day in range(3):
        day_start = LOSS_START + timedelta(days=day)
        rows = client.get("/transformers/TR-00001/energy",
                        params={"start": day_start.isoformat(), "end": (day_start + timedelta(days=1)).isoformat()}).json()["readings"]
        delivered = sum(r["delivered_kwh"] for r in rows)
        meters = sum(metered(datetime.fromisoformat(r["interval_start"])) for r in rows)
        assert (delivered - meters) / meters == pytest.approx(0.15, abs=1e-3)
