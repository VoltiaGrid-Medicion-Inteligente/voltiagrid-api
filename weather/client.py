"""F6: hourly temperature forecast from Open-Meteo (US-20, T-20.1).

    https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m&timezone=UTC

Public API, no key. Every request has a timeout; transient failures (network
errors, timeouts, 429 and 5xx) are retried with exponential backoff
(1 s, 2 s, 4 s ...). Other 4xx are not retried: they will not fix themselves.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

BASE_URL = "https://api.open-meteo.com"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class City:
    name: str
    latitude: float
    longitude: float


CITIES = {"london": City("london", 51.5072, -0.1276)}


class ForecastUnavailable(Exception):
    """Open-Meteo did not answer after every retry, or answered with a non-retryable error."""


class OpenMeteoClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        max_attempts: int = 4,
        backoff_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=timeout_seconds)
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep
        self.attempts = 0  

    def hourly_forecast(self, city: City, days: int = 2) -> dict:
        """The JSON Open-Meteo returns, untouched."""
        params = {
            "latitude": city.latitude,
            "longitude": city.longitude,
            "hourly": "temperature_2m",
            "timezone": "UTC",
            "forecast_days": days,
        }
        last_error = "no attempt"
        for attempt in range(1, self.max_attempts + 1):
            self.attempts = attempt
            try:
                response = self.http.get("/v1/forecast", params=params)
            except httpx.TransportError as exc:  
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    return response.json()
                if response.status_code not in RETRYABLE_STATUS:
                    raise ForecastUnavailable(f"Open-Meteo answered {response.status_code}: {response.text[:200]}")
                last_error = f"HTTP {response.status_code}"
            if attempt < self.max_attempts:
                self.sleep(self.backoff_seconds * 2 ** (attempt - 1))
        raise ForecastUnavailable(f"Open-Meteo failed {self.max_attempts} times; last error: {last_error}")
