"""US-20 (T-20.3): F6 client tests with a mocked Open-Meteo. No test calls the real API:
every request goes through httpx.MockTransport, and an unexpected request fails the test."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from weather.__main__ import build_parser, run
from weather.client import CITIES, ForecastUnavailable, OpenMeteoClient
from weather.heat_wave import apply_heat_wave

NOW = datetime(2026, 7, 1, 6, 30, tzinfo=timezone.utc)
FORECAST = {
    "latitude": 51.5, "longitude": -0.12,
    "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
    "hourly": {
        "time": [f"2026-07-01T{h:02d}:00" for h in range(24)],
        "temperature_2m": [14.0 + h * 0.5 for h in range(24)],
    },
}


class FakeOpenMeteo:
    """Answers from a script, one item per request; records every request."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.url.host == "api.open-meteo.com", f"unexpected host {request.url.host}"
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(fake: FakeOpenMeteo, sleeps: list | None = None, attempts: int = 4) -> OpenMeteoClient:
    http = httpx.Client(base_url="https://api.open-meteo.com", transport=httpx.MockTransport(fake))
    return OpenMeteoClient(http=http, max_attempts=attempts, sleep=(sleeps.append if sleeps is not None else lambda s: None))


def args_for(tmp_path, *extra):
    return build_parser().parse_args(["--raw-dir", str(tmp_path), *extra])


# ---------- success ----------

def test_success_on_first_attempt_stores_the_untouched_answer(tmp_path):
    fake = FakeOpenMeteo(httpx.Response(200, json=FORECAST))
    path = run(args_for(tmp_path), client=make_client(fake), now=NOW)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["response"] == FORECAST
    assert stored["mode"] == "real" and stored["attempts"] == 1
    assert stored["fetched_at"] == "2026-07-01T06:30:00Z"
    assert len(fake.requests) == 1


def test_request_asks_for_hourly_temperature_of_the_city_in_utc(tmp_path):
    fake = FakeOpenMeteo(httpx.Response(200, json=FORECAST))
    run(args_for(tmp_path, "--days", "3"), client=make_client(fake), now=NOW)
    params = fake.requests[0].url.params
    london = CITIES["london"]
    assert fake.requests[0].url.path == "/v1/forecast"
    assert float(params["latitude"]) == london.latitude and float(params["longitude"]) == london.longitude
    assert params["hourly"] == "temperature_2m" and params["timezone"] == "UTC" and params["forecast_days"] == "3"


# ---------- retries ----------

@pytest.mark.parametrize("failure", [
    httpx.Response(503),
    httpx.Response(429),
    httpx.ReadTimeout("timed out"),
    httpx.ConnectError("connection refused"),
])
def test_transient_failures_are_retried(tmp_path, failure):
    fake = FakeOpenMeteo(failure, httpx.Response(200, json=FORECAST))
    client = make_client(fake)
    path = run(args_for(tmp_path), client=client, now=NOW)
    assert client.attempts == 2 and path.exists()


def test_backoff_doubles_between_attempts(tmp_path):
    sleeps = []
    fake = FakeOpenMeteo(httpx.Response(500), httpx.Response(502), httpx.Response(504), httpx.Response(200, json=FORECAST))
    run(args_for(tmp_path), client=make_client(fake, sleeps), now=NOW)
    assert sleeps == [1.0, 2.0, 4.0]


# ---------- final failure ----------

def test_final_failure_raises_and_writes_nothing(tmp_path):
    fake = FakeOpenMeteo(*[httpx.Response(503)] * 4)
    client = make_client(fake)
    with pytest.raises(ForecastUnavailable, match="failed 4 times"):
        run(args_for(tmp_path), client=client, now=NOW)
    assert len(fake.requests) == 4
    assert not any(tmp_path.rglob("*.json"))


def test_client_errors_are_not_retried(tmp_path):
    fake = FakeOpenMeteo(httpx.Response(400, json={"error": True, "reason": "bad latitude"}))
    with pytest.raises(ForecastUnavailable, match="400"):
        run(args_for(tmp_path), client=make_client(fake), now=NOW)
    assert len(fake.requests) == 1


# ---------- heat-wave mode ----------

def test_heat_wave_raises_afternoon_and_evening_above_30_degrees(tmp_path):
    fake = FakeOpenMeteo(httpx.Response(200, json=FORECAST))
    path = run(args_for(tmp_path, "--heat-wave"), client=make_client(fake), now=NOW)
    stored = json.loads(path.read_text(encoding="utf-8"))
    hourly = stored["response"]["hourly"]
    assert stored["mode"] == "heat_wave"
    for hour, (temp, real) in enumerate(zip(hourly["temperature_2m"], hourly["original_temperature_2m"])):
        if 12 <= hour < 22:
            assert temp > 30
        else:
            assert temp == real
    assert hourly["original_temperature_2m"] == FORECAST["hourly"]["temperature_2m"]


def test_heat_wave_keeps_hotter_real_values():
    hot = {"hourly": {"time": ["2026-07-01T15:00"], "temperature_2m": [35.5]}}
    assert apply_heat_wave(hot)["hourly"]["temperature_2m"] == [35.5]


def test_heat_wave_threshold_must_be_above_30():
    with pytest.raises(ValueError):
        apply_heat_wave(FORECAST, min_c=29.0)


def test_heat_wave_from_environment_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("F6_HEAT_WAVE", "true")
    assert build_parser().parse_args([]).heat_wave is True
