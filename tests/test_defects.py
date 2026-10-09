"""T-02.3 (KAN-76): injected defect rates must stay within ±1 percentage point."""

import random
from datetime import datetime, timedelta

import pytest

from seed.defects import (
    DefectCatalog,
    apply_defects,
    inject_duplicate,
    inject_null,
    inject_offset_clock,
    inject_out_of_bounds,
    should_skip_day,
)

N_READINGS = 50_000
TOLERANCE = 0.01  # ±1 percentage point


def make_readings(n: int) -> list:
    """Clean half-hourly readings: values between 0.05 and 2.0 kWh, timestamps on :00/:30."""
    rng = random.Random(0)
    start = datetime(2013, 1, 1)
    return [
        {
            "meter_id": f"MAC{i % 200:06d}",
            "timestamp": start + timedelta(minutes=30 * (i // 200)),
            "energy_kwh": round(rng.uniform(0.05, 2.0), 3),
        }
        for i in range(n)
    ]


@pytest.fixture(scope="module")
def readings():
    return make_readings(N_READINGS)


# --- Rate tests (±1%) --------------------------------------------------------

@pytest.mark.parametrize("rate", [0.02, 0.05, 0.10])
def test_each_defect_rate_within_tolerance(readings, rate):
    catalog = DefectCatalog(base_rate=rate)
    _, counts = apply_defects(readings, catalog, random.Random(42))

    for defect, count in counts.items():
        observed = count / len(readings)
        assert abs(observed - rate) <= TOLERANCE, (
            f"{defect}: observed {observed:.4f}, expected {rate} ± {TOLERANCE}"
        )


def test_rates_can_be_set_per_defect_type(readings):
    catalog = DefectCatalog(base_rate=0.02)
    catalog.null_rate = 0.08
    catalog.duplicate_rate = 0.0
    _, counts = apply_defects(readings, catalog, random.Random(42))

    assert abs(counts["null"] / len(readings) - 0.08) <= TOLERANCE
    assert abs(counts["out_of_bounds"] / len(readings) - 0.02) <= TOLERANCE
    assert counts["duplicate"] == 0


@pytest.mark.parametrize("rate", [0.02, 0.10])
def test_missing_day_rate_within_tolerance(rate):
    rng = random.Random(42)
    meter_days = 50_000
    skipped = sum(should_skip_day(rng, rate) for _ in range(meter_days))
    assert abs(skipped / meter_days - rate) <= TOLERANCE


def test_rate_zero_injects_nothing(readings):
    catalog = DefectCatalog(base_rate=0.0)
    result, counts = apply_defects(readings, catalog, random.Random(42))

    assert all(c == 0 for c in counts.values())
    assert result == readings


# --- Reproducibility ---------------------------------------------------------

def test_same_seed_gives_same_output(readings):
    catalog = DefectCatalog(base_rate=0.05)
    first = apply_defects(readings, catalog, random.Random(7))
    second = apply_defects(readings, catalog, random.Random(7))
    assert first == second


def test_input_is_not_modified(readings):
    snapshot = [dict(r) for r in readings[:1000]]
    apply_defects(readings[:1000], DefectCatalog(base_rate=0.5), random.Random(1))
    assert readings[:1000] == snapshot


# --- Shape of each defect ----------------------------------------------------

def base_reading():
    return {"meter_id": "MAC000001", "timestamp": datetime(2013, 1, 1, 10, 30), "energy_kwh": 0.8}


def test_null_defect_sets_null_value():
    rng = random.Random(1)
    for _ in range(50):
        assert inject_null(base_reading(), rng)["energy_kwh"] in (None, "Null")


def test_out_of_bounds_is_negative_or_above_25():
    rng = random.Random(1)
    for _ in range(200):
        value = inject_out_of_bounds(base_reading(), rng)["energy_kwh"]
        assert value < 0 or value > 25


def test_offset_clock_leaves_the_half_hour_grid():
    rng = random.Random(1)
    for _ in range(200):
        ts = inject_offset_clock(base_reading(), rng)["timestamp"]
        assert ts.minute not in (0, 30)
        assert abs(ts - base_reading()["timestamp"]) <= timedelta(minutes=14)


def test_duplicate_same_meter_and_interval_different_value():
    rng = random.Random(1)
    original, duplicate = inject_duplicate(base_reading(), rng)
    assert duplicate["meter_id"] == original["meter_id"]
    assert duplicate["timestamp"] == original["timestamp"]
    assert duplicate["energy_kwh"] != original["energy_kwh"]