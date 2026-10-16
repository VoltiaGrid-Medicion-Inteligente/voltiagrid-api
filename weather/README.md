# F6: temperature forecast (Open-Meteo)

Hourly temperature forecast for the pilot city, stored untouched in the raw layer (US-20).
RN-08 uses it: a demand-response event needs a forecast above 30 °C.

```bash
python -m weather                  
python -m weather --days 3
python -m weather --heat-wave      
```

| Option | Env variable | Default |
|---|---|---|
| `--city` | `F6_CITY` | `london` |
| `--days` | `F6_FORECAST_DAYS` | `2` |
| `--raw-dir` | `RAW_DIR` | `data/raw` |
| `--attempts` | `F6_MAX_ATTEMPTS` | `4` |
| `--heat-wave` | `F6_HEAT_WAVE=true` | off |
| `--heat-wave-min-c` | `F6_HEAT_WAVE_MIN_C` | `32.0` (must be above 30) |

- Timeout of 10 s per request. Network errors, timeouts, 429 and 5xx are retried with backoff 1 s, 2 s, 4 s; other 4xx fail at once.
- Output: `data/raw/f6_weather/city=london/date=YYYY-MM-DD/forecast_YYYYMMDDTHHMMSSZ.json` with the Open-Meteo answer under `response`.
- Exit code 1 (and no file) if Open-Meteo is still failing after the last attempt.

## Heat-wave mode (T-20.2)

London rarely passes 30 °C, so RN-08 (event if the forecast is above 30 °C and the projected load above 85% of the
circuit capacity) would never fire in a demo. With `--heat-wave` the hours from 12:00 to 21:59 UTC (they cover the
F7 peak band, 18:00-22:00) get at least `--heat-wave-min-c` °C; the other hours keep the real forecast.

The file is still stored in raw, marked as simulated: `"mode": "heat_wave"` in the envelope and the real values
under `response.hourly.original_temperature_2m`. Real runs have `"mode": "real"`.