"""Store each forecast in the raw layer, untouched (US-20, T-20.1; ADR-007 raw first).

    <RAW_DIR>/f6_weather/city=<city>/date=<YYYY-MM-DD>/forecast_<YYYYMMDDTHHMMSSZ>.json

RAW_DIR is `data/raw` locally (git-ignored). When the S3 raw bucket exists
(US-23) the same relative path is used as the object key.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def raw_path(raw_dir: Path, city: str, fetched_at: datetime) -> Path:
    ts = fetched_at.astimezone(timezone.utc)
    return raw_dir / "f6_weather" / f"city={city}" / f"date={ts:%Y-%m-%d}" / f"forecast_{ts:%Y%m%dT%H%M%SZ}.json"


def write_raw(raw_dir: Path, city: str, response: dict, fetched_at: datetime, metadata: dict | None = None) -> Path:
    path = raw_path(raw_dir, city, fetched_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "source": "open-meteo",
        "city": city,
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        **(metadata or {}),
        "response": response,
    }
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return path
