# F6: temperature forecast (Open-Meteo)

Hourly temperature forecast for the pilot city, stored untouched in the raw layer (US-20).
RN-08 uses it: a demand-response event needs a forecast above 30 °C.

```bash
python -m weather                 
python -m weather --days 3
```

| Option | Env variable | Default |
|---|---|---|
| `--city` | `F6_CITY` | `london` |
| `--days` | `F6_FORECAST_DAYS` | `2` |
| `--raw-dir` | `RAW_DIR` | `data/raw` |
| `--attempts` | `F6_MAX_ATTEMPTS` | `4` |

- Timeout of 10 s per request. Network errors, timeouts, 429 and 5xx are retried with backoff 1 s, 2 s, 4 s; other 4xx fail at once.
- Output: `data/raw/f6_weather/city=london/date=YYYY-MM-DD/forecast_YYYYMMDDTHHMMSSZ.json` with the Open-Meteo answer under `response`.
- Exit code 1 (and no file) if Open-Meteo is still failing after the last attempt.
