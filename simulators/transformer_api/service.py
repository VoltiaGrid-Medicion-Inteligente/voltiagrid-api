"""Energy delivered to a transformer every 15 minutes (US-15, T-15.1).

delivered = sum of what its meters recorded in the interval

It uses the same consumption model and seed as the F3 simulator
(`simulators.common.consumption`), so F5 and F3 agree for the same meters.
"""

from datetime import datetime

from simulators.common.consumption import QUARTER_HOUR, floor_to, quarter_hour_kwh
from simulators.common.inventory import Inventory


def metered_kwh(inventory: Inventory, transformer_code: str, interval_start: datetime, seed: int) -> float:
    return sum(quarter_hour_kwh(m, interval_start, seed) for m in inventory.meters_of(transformer_code))


def delivered_series(
    inventory: Inventory,
    transformer_code: str,
    start: datetime,
    end: datetime,
    seed: int,
) -> list[dict]:
    """One row per 15-minute interval in [start, end)."""
    rows = []
    ts = floor_to(start, QUARTER_HOUR)
    while ts < end:
        rows.append({"interval_start": ts, "delivered_kwh": round(metered_kwh(inventory, transformer_code, ts, seed), 4)})
        ts += QUARTER_HOUR
    return rows