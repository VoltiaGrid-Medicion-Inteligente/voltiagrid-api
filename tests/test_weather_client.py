"""US-20 (T-20.1): a temporary failure of Open-Meteo is retried and the forecast lands in raw."""

import json
from datetime import datetime, timezone

import httpx

from weather.__main__ import build_parser, run
from weather.client import OpenMeteoClient

FORECAST = {"latitude": 51.5, "longitude": -0.12, "hourly_units": {"temperature_2m": "°C"},
            "hourly": {"time": ["2026-07-01T00:00", "2026-07-01T01:00"], "temperature_2m": [14.2, 13.8]}}


def test_temporary_failure_is_retried_and_the_file_lands_in_raw(tmp_path):
    answers = iter([httpx.Response(503), httpx.Response(200, json=FORECAST)])
    http = httpx.Client(base_url="https://api.open-meteo.com", transport=httpx.MockTransport(lambda req: next(answers)))
    client = OpenMeteoClient(http=http, sleep=lambda s: None)

    args = build_parser().parse_args(["--raw-dir", str(tmp_path)])
    path = run(args, client=client, now=datetime(2026, 7, 1, 6, 0, tzinfo=timezone.utc))

    assert client.attempts == 2
    assert path == tmp_path / "f6_weather" / "city=london" / "date=2026-07-01" / "forecast_20260701T060000Z.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["response"] == FORECAST
    assert stored["attempts"] == 2
