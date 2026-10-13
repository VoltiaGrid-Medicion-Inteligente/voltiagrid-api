from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.inventory import Meter, Transformer

SYNTHETIC_METERS_PER_TRANSFORMER = 64


@dataclass(frozen=True)
class Inventory:
    meters_by_transformer: dict[str, list[str]]

    @property
    def meter_count(self) -> int:
        return sum(len(m) for m in self.meters_by_transformer.values())

    def meters_of(self, transformer_code: str) -> list[str]:
        return self.meters_by_transformer.get(transformer_code, [])


def concentrator_id(transformer_code: str) -> str:
    return f"DC-{transformer_code}"


def load_from_db(database_url: str) -> Inventory:
    engine = create_engine(database_url)
    with Session(engine) as session:
        rows = session.execute(
            select(Transformer.code, Meter.lclid)
            .join(Meter, Meter.transformer_id == Transformer.id)
            .order_by(Transformer.code, Meter.lclid)
        ).all()
    grouped: dict[str, list[str]] = defaultdict(list)
    for tx_code, lclid in rows:
        grouped[tx_code].append(lclid)
    return Inventory(dict(grouped))


def with_volume(base: Inventory, target_meters: int) -> Inventory:
    if target_meters <= 0:
        raise ValueError("target_meters must be positive")

    result: dict[str, list[str]] = {}
    remaining = target_meters
    for tx_code in sorted(base.meters_by_transformer):
        if remaining == 0:
            break
        meters = base.meters_by_transformer[tx_code][:remaining]
        result[tx_code] = meters
        remaining -= len(meters)

    sim_index = 1
    tx_index = 1
    while remaining > 0:
        count = min(SYNTHETIC_METERS_PER_TRANSFORMER, remaining)
        result[f"TR-S{tx_index:05d}"] = [f"SIM{sim_index + i:07d}" for i in range(count)]
        sim_index += count
        tx_index += 1
        remaining -= count
    return Inventory(result)