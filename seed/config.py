import os
from dataclasses import dataclass

VALID_MODES = ("dev", "full")
METERS_BY_MODE = {"dev": 200, "full": 5500}

@dataclass(frozen=True)
class SeedSettings:
    seed: int
    mode: str
    defect_rate: float
    database_url: str

    @property
    def meter_count(self) -> int:
        return METERS_BY_MODE[self.mode]

def first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None

def build_settings(args):
    raw_seed = first_not_none(args.seed, os.getenv("SEED"), 42)
    seed = int(raw_seed)

    mode = first_not_none(args.mode, os.getenv("MODE"), "dev")
    if mode not in VALID_MODES:
        raise ValueError(F"MODE debe ser uno de {VALID_MODES}, pero llegó '{mode}'")

    raw_defect_rate = first_not_none(args.defect_rate, os.getenv("DEFECT_RATE"), 0.02)
    defect_rate = float(raw_defect_rate)
    if not 0 <= defect_rate <= 1:
        raise ValueError(f"DEFECT_RATE debe estar entre 0 y 1, pero llegó '{defect_rate}'")

    database_url = first_not_none(args.database_url, os.getenv("DATABASE_URL"))
    if database_url is None:
        raise ValueError("Falta DATABASE_URL (variable de entorno, .env 0 --database-url)")
    
    return SeedSettings(
        seed=seed,
        mode=mode,
        defect_rate=defect_rate,
        database_url=database_url,
    )