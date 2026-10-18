"""US-13 (T-13.2): every 30-minute reading falls in exactly one F7 band with the price of its date."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.tariffs import TariffCalendar

CALENDAR = TariffCalendar.from_csv("data/reference/tariffs.csv")


@pytest.mark.parametrize("hhmm,band", [
    ("00:00", "off-peak"), ("07:30", "off-peak"), ("08:00", "intermediate"), ("17:30", "intermediate"),
    ("18:00", "peak"), ("21:30", "peak"), ("22:00", "off-peak"), ("23:30", "off-peak"),
])
def test_band_by_time_of_day(hhmm, band):
    h, m = map(int, hhmm.split(":"))
    assert CALENDAR.band_for(datetime(2013, 3, 4, h, m, tzinfo=timezone.utc)).band_name == band


def test_price_depends_on_the_validity_period():
    assert CALENDAR.band_for(datetime(2011, 12, 1, 19, 0)).price_per_kwh == Decimal("0.25")
    assert CALENDAR.band_for(datetime(2013, 12, 1, 19, 0)).price_per_kwh == Decimal("0.30")


def test_a_day_has_20_off_peak_20_intermediate_and_8_peak_readings():
    start = datetime(2013, 3, 4, tzinfo=timezone.utc)
    bands = [CALENDAR.band_for(start + i * timedelta(minutes=30)).band_name for i in range(48)]
    assert (bands.count("off-peak"), bands.count("intermediate"), bands.count("peak")) == (20, 20, 8)
