"""Energy delivered to a transformer every 15 minutes (US-15, T-15.1 and T-15.2).

delivered = (sum of what its meters recorded) x (1 + injected loss)

Without injected losses, delivered equals the sum of its meters, which is what
F3 sends for the same meters and the same seed. With a 15% loss, delivered is
15% higher than what the meters recorded: that difference is what RN-06 must
find (loss above 12% for 3 days in a row = suspicious transformer).
"""

from datetime import datetime

from simulators.common.consumption import QUARTER_HOUR, floor_to, quarter_hour_kwh
from simulators.common.inventory import Inventory
from simulators.transformer_api.losses import LossStore


def metered_kwh(inventory: Inventory, transformer_code: str, interval_start: datetime, seed: int) -> float:
    return sum(quarter_hour_kwh(m, interval_start, seed) for m in inventory.meters_of(transformer_code))


def delivered_series(
    inventory: Inventory,
    losses: LossStore,
    transformer_code: str,
    start: datetime,
    end: datetime,
    seed: int,
) -> list[dict]:
    """One row per 15-minute interval in [start, end)."""
    rows = []
    ts = floor_to(start, QUARTER_HOUR)
    while ts < end:
        metered = metered_kwh(inventory, transformer_code, ts, seed)
        loss = losses.loss_for(transformer_code, ts)
        rows.append({"interval_start": ts, "delivered_kwh": round(metered * (1 + loss), 4)})
        ts += QUARTER_HOUR
    return rows
