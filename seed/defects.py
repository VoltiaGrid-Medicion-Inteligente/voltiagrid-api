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