"""Fetch the hourly temperature forecast (F6) and store it in raw (US-20).

    python -m weather                       # London, 2 days, into data/raw
    python -m weather --days 3 --raw-dir data/raw
    python -m weather --heat-wave           # simulated heat wave above 30 °C (T-20.2)
"""


import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


from weather.client import CITIES, ForecastUnavailable, OpenMeteoClient
from weather.heat_wave import HEAT_WAVE_MIN_C, apply_heat_wave
from weather.raw import write_raw


def build_parser() -> argparse.ArgumentParser:
    env = os.getenv
    p = argparse.ArgumentParser(description="F6 temperature forecast (Open-Meteo) to raw")
    p.add_argument("--city", choices=sorted(CITIES), default=env("F6_CITY") or "london")
    p.add_argument("--days", type=int, default=int(env("F6_FORECAST_DAYS") or "2"))
    p.add_argument("--raw-dir", type=Path, default=Path(env("RAW_DIR") or "data/raw"))
    p.add_argument("--attempts", type=int, default=int(env("F6_MAX_ATTEMPTS") or "4"))
    p.add_argument("--heat-wave", action="store_true", default=(env("F6_HEAT_WAVE") or "").lower() in ("1", "true", "yes"),
                   help="simulate a heat wave: afternoon and evening hours at least --heat-wave-min-c")
    p.add_argument("--heat-wave-min-c", type=float, default=float(env("F6_HEAT_WAVE_MIN_C") or HEAT_WAVE_MIN_C))
    return p



def run(args, client: OpenMeteoClient | None = None, now: datetime | None = None) -> Path:
    client = client or OpenMeteoClient(max_attempts=args.attempts)
    city = CITIES[args.city]
    response = client.hourly_forecast(city, days=args.days)
    metadata = {"attempts": client.attempts, "mode": "real"}
    if args.heat_wave:
        response = apply_heat_wave(response, min_c=args.heat_wave_min_c)
        metadata.update(mode="heat_wave", heat_wave_min_c=args.heat_wave_min_c)
    fetched_at = now or datetime.now(timezone.utc)
    return write_raw(args.raw_dir, city.name, response, fetched_at, metadata)




def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()
    try:
        path = run(args)
    except ForecastUnavailable as exc:
        print(f"F6 forecast not stored: {exc}", file=sys.stderr)
        return 1
    print(f"written {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
