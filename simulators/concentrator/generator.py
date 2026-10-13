import hashlib
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from seed.defects import DefectCatalog, apply_defects, should_skip_day
from simulators.common.consumption import HALF_HOUR, half_hour_kwh
from simulators.common.inventory import Inventory, concentrator_id
from simulators.concentrator.contract import SCHEMA_VERSION

LIVE_ROUTING_KEY = "readings.live"
RESEND_ROUTING_KEY = "readings.resend"


def _rng(*parts) -> random.Random:
    key = "|".join(str(p) for p in parts).encode()
    return random.Random(int(hashlib.sha256(key).hexdigest()[:16], 16))


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Outage:
    concentrator_id: str
    start: datetime
    end: datetime

    def covers(self, ts: datetime) -> bool:
        return self.start <= ts < self.end


@dataclass(frozen=True)
class Envelope:
    routing_key: str
    message: dict


@dataclass
class ConcentratorSimulator:
    inventory: Inventory
    seed: int = 42
    catalog: DefectCatalog = field(default_factory=lambda: DefectCatalog(base_rate=0.02))
    gap_rate: float = 0.02
    outages: list[Outage] = field(default_factory=list)

    def __post_init__(self):
        self._sequence: Counter = Counter()
        self._reading_seq: Counter = Counter()
        self._buffer: dict[str, list[dict]] = {}
        self.stats: Counter = Counter()

    def concentrators(self) -> list[str]:
        return [concentrator_id(tx) for tx in sorted(self.inventory.meters_by_transformer)]

    def _in_outage(self, cid: str, ts: datetime) -> bool:
        return any(o.concentrator_id == cid and o.covers(ts) for o in self.outages)

    def _readings(self, tx_code: str, cid: str, interval_start: datetime) -> list[dict]:
        rng = _rng(self.seed, cid, interval_start.isoformat())
        clean = []
        for meter_id in self.inventory.meters_of(tx_code):
            self.stats["expected"] += 1
            day_rng = _rng(self.seed, "day", meter_id, interval_start.date().isoformat())
            if should_skip_day(day_rng, self.catalog.missing_day_rate):
                self.stats["missing_day"] += 1
                continue
            if rng.random() < self.gap_rate:
                self.stats["gap"] += 1
                continue
            clean.append(
                {
                    "meter_id": meter_id,
                    "timestamp": interval_start,
                    "energy_kwh": half_hour_kwh(meter_id, interval_start, self.seed),
                }
            )
        dirty, counts = apply_defects(clean, self.catalog, rng)
        self.stats.update(counts)

        readings = []
        for r in dirty:
            self._reading_seq[cid] += 1
            readings.append(
                {
                    "meter_id": r["meter_id"],
                    "interval_start": _iso(r["timestamp"]),
                    "energy_kwh": r["energy_kwh"],
                    "reading_seq": self._reading_seq[cid],
                }
            )
        return readings

    def _build(self, tx_code: str, cid: str, interval_start: datetime) -> dict | None:
        readings = self._readings(tx_code, cid, interval_start)
        if not readings:
            return None
        self._sequence[cid] += 1
        seq = self._sequence[cid]
        return {
            "schema_version": SCHEMA_VERSION,
            "message_id": f"{cid}-{seq:08d}",
            "concentrator_id": cid,
            "sequence": seq,
            "sent_at": None,
            "is_resend": False,
            "readings": readings,
        }

    def tick(self, interval_start: datetime, sent_at: datetime | None = None) -> list[Envelope]:
        if interval_start.tzinfo is None:
            raise ValueError("interval_start must be timezone-aware (UTC)")
        sent_at = sent_at or interval_start + HALF_HOUR
        out: list[Envelope] = []

        for tx_code in sorted(self.inventory.meters_by_transformer):
            cid = concentrator_id(tx_code)
            message = self._build(tx_code, cid, interval_start)

            if self._in_outage(cid, interval_start):
                if message:
                    self._buffer.setdefault(cid, []).append(message)
                continue

            for held in self._buffer.pop(cid, []):
                held["is_resend"] = True
                held["sent_at"] = _iso(sent_at)
                out.append(Envelope(RESEND_ROUTING_KEY, held))
                self.stats["resent_messages"] += 1

            if message:
                message["sent_at"] = _iso(sent_at)
                out.append(Envelope(LIVE_ROUTING_KEY, message))
        return out

    def pending_resend(self) -> int:
        return sum(len(v) for v in self._buffer.values())


def outages_for_meters(inventory: Inventory, meters: int, start: datetime, hours: float) -> list[Outage]:
    outages, affected = [], 0
    end = start + timedelta(hours=hours)
    for tx_code in sorted(inventory.meters_by_transformer):
        if affected >= meters:
            break
        outages.append(Outage(concentrator_id(tx_code), start, end))
        affected += len(inventory.meters_of(tx_code))
    return outages
