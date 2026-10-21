"""Client of the F5 transformer metering API (US-19, T-19.1).

The control center does not compute load itself: it reads the energy F5
delivers to each transformer every 15 minutes, so its numbers match F5 exactly.
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from app.core.config import get_settings
from app.core.errors import NotFoundError


class F5Unavailable(Exception):
    """F5 did not answer, or answered with an unexpected error."""


class F5Client:
    def __init__(self, http: httpx.Client):
        self.http = http

    def energy(self, transformer_code: str, start: datetime, end: datetime) -> list[tuple[datetime, float]]:
        """(interval_start, delivered_kwh) every 15 minutes in [start, end)."""
        try:
            r = self.http.get(
                f"/transformers/{transformer_code}/energy",
                params={"start": start.isoformat(), "end": end.isoformat()},
            )
        except httpx.HTTPError as exc:
            raise F5Unavailable(str(exc)) from exc
        if r.status_code == 404:
            raise NotFoundError("Transformer", transformer_code)
        if r.status_code != 200:
            raise F5Unavailable(f"F5 answered {r.status_code}")
        return [(datetime.fromisoformat(x["interval_start"]), x["delivered_kwh"]) for x in r.json()["readings"]]


def get_f5_client() -> Iterator[F5Client]:
    """FastAPI dependency. Tests replace it with a client on the F5 app itself."""
    with httpx.Client(base_url=get_settings().f5_url, timeout=10) as http:
        yield F5Client(http)
