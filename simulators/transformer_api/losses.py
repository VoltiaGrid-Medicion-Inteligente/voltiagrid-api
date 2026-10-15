"""Loss injections: a percentage of extra energy delivered to a transformer in a period (T-15.2).

Kept in memory on purpose: F5 is a simulated source and an injection only lives
for a demo or a test. Restarting the API clears them; run it with one worker so
every request sees the same store.
"""

from dataclasses import dataclass
from datetime import datetime
from itertools import count
from threading import Lock


@dataclass(frozen=True)
class LossInjection:
    id: int
    transformer_code: str
    start: datetime
    end: datetime
    loss_pct: float

    def covers(self, transformer_code: str, ts: datetime) -> bool:
        return self.transformer_code == transformer_code and self.start <= ts < self.end


class LossStore:
    def __init__(self):
        self._items: dict[int, LossInjection] = {}
        self._ids = count(1)
        self._lock = Lock()

    def add(self, transformer_code: str, start: datetime, end: datetime, loss_pct: float) -> LossInjection:
        with self._lock:
            item = LossInjection(next(self._ids), transformer_code, start, end, loss_pct)
            self._items[item.id] = item
            return item

    def all(self) -> list[LossInjection]:
        return sorted(self._items.values(), key=lambda i: i.id)

    def remove(self, injection_id: int) -> bool:
        with self._lock:
            return self._items.pop(injection_id, None) is not None

    def loss_for(self, transformer_code: str, ts: datetime) -> float:
        """Total injected loss for one transformer in the interval starting at ts."""
        return sum(i.loss_pct for i in self._items.values() if i.covers(transformer_code, ts))