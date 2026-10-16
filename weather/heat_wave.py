"""Heat-wave simulation mode for F6 (US-20, T-20.2).

London rarely passes 30 °C, so the demand-response rule (RN-08: forecast above
30 °C and projected load above 85% of the circuit) would never fire in a demo.
This mode raises the forecast of the afternoon and evening hours to at least
`min_c` (32 °C by default) so the rule can be tested end to end.

Hours outside the window keep the real value. The stored file says
`"mode": "heat_wave"` and keeps the real temperatures under `original_temperature_2m`,
so simulated data is never mistaken for a real forecast.
"""

import copy
from datetime import datetime

HEAT_WAVE_MIN_C = 32.0
WINDOW = (12, 22)  


def apply_heat_wave(response: dict, min_c: float = HEAT_WAVE_MIN_C, window: tuple[int, int] = WINDOW) -> dict:
    if min_c <= 30:
        raise ValueError("min_c must be above 30 °C, the RN-08 threshold")
    result = copy.deepcopy(response)
    hourly = result["hourly"]
    original = list(hourly["temperature_2m"])
    start_hour, end_hour = window
    hourly["temperature_2m"] = [
        max(t, min_c) if t is not None and start_hour <= datetime.fromisoformat(ts).hour < end_hour else t
        for ts, t in zip(hourly["time"], original)
    ]
    hourly["original_temperature_2m"] = original
    return result
