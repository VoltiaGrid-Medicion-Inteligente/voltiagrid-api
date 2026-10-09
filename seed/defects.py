import random
from datetime import timedelta

# T-02.1: Defect catalog and configuration
class DefectCatalog:
    def __init__(self, base_rate: float = 0.02):
        """
        Takes DEFECT_RATE as the default value,
        but allows adjusting each type separately.
        """
        self.null_rate = base_rate
        self.duplicate_rate = base_rate
        self.offset_clock_rate = base_rate
        self.out_of_bounds_rate = base_rate
        self.missing_day_rate = base_rate


# T-02.2: One function per defect
# All of them receive the 'rng' (random.Random) object to ensure reproducibility.

def inject_null(reading: dict, rng: random.Random) -> dict:
    """
    Injects null readings.
    Randomly chooses between injecting the None value or the string "Null".
    """
    reading['energy_kwh'] = rng.choice([None, "Null"])
    return reading

def inject_duplicate(reading: dict, rng: random.Random) -> list:
    """
    Generates duplicates for the same meter and interval.
    The duplicate has different energy values.
    Returns a list with the original reading and the duplicate.
    """
    duplicate = reading.copy()
    # If the reading has a valid numeric value, we alter it
    if isinstance(reading.get('energy_kwh'), (int, float)):
        # Multiply by a random factor so the value is different
        duplicate['energy_kwh'] = round(reading['energy_kwh'] * rng.uniform(0.5, 1.5), 2)
    return [reading, duplicate]

def inject_offset_clock(reading: dict, rng: random.Random) -> dict:
    """
    Offsets the clock.
    Adds or subtracts minutes so the time doesn't fall exactly on :00 or :30.
    """
    # Choose a random offset between 1 and 14 minutes (positive or negative)
    offset = rng.choice(list(range(1, 15)) + list(range(-14, 0)))
    reading['timestamp'] = reading['timestamp'] + timedelta(minutes=offset)
    return reading

def inject_out_of_bounds(reading: dict, rng: random.Random) -> dict:
    """
    Injects negative values or physically impossible peaks.
    Chooses between a negative value or a peak greater than 25 kWh.
    """
    if rng.choice([True, False]):
        # Negative value between -5 and -0.1
        reading['energy_kwh'] = round(rng.uniform(-5.0, -0.1), 2) 
    else:
        # Peak greater than 25 kWh
        reading['energy_kwh'] = round(rng.uniform(25.1, 50.0), 2) 
    return reading

def should_skip_day(rng: random.Random, missing_day_rate: float) -> bool:
    """
    Determines if a full day without reporting from a meter should occur.
    This function would be called from the main loop that generates the days.
    """
    return rng.random() < missing_day_rate

# T-02.3: Apply the catalog to a batch of readings and count what was injected.

def apply_defects(readings: list, catalog: DefectCatalog, rng: random.Random) -> tuple:
    """
    Applies the catalog rates to a list of readings.
    - null and out_of_bounds both change energy_kwh, so only one of them
      can hit the same reading (one roll, consecutive thresholds).
    - offset_clock and duplicate are rolled independently.
    Returns (new_readings, counts) where counts has one entry per defect type.
    The input list is not modified.
    """
    counts = {"null": 0, "out_of_bounds": 0, "offset_clock": 0, "duplicate": 0}
    result = []
    for original in readings:
        reading = dict(original)

        roll = rng.random()
        if roll < catalog.null_rate:
            reading = inject_null(reading, rng)
            counts["null"] += 1
        elif roll < catalog.null_rate + catalog.out_of_bounds_rate:
            reading = inject_out_of_bounds(reading, rng)
            counts["out_of_bounds"] += 1

        if rng.random() < catalog.offset_clock_rate:
            reading = inject_offset_clock(reading, rng)
            counts["offset_clock"] += 1

        if rng.random() < catalog.duplicate_rate:
            result.extend(inject_duplicate(reading, rng))
            counts["duplicate"] += 1
        else:
            result.append(reading)

    return result, counts