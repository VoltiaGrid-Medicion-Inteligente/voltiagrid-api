"""Settings of the APIs, read from environment variables (never from the repo).

Locally they come from `.env` (copy `.env.example`); in docker-compose and AWS
they are injected as environment variables.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

from app.core.database_url import require_database_url

load_dotenv()



def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set (see .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "voltiagrid"
    jwt_expire_minutes: int = 60
    model_seed: int = 42
    defect_rate: float = 0.02
    tariffs_csv: str = "data/reference/tariffs.csv"
    f5_url: str = "http://localhost:8005"

    @property
    def database_url(self) -> str:
        return require_database_url()

    @property
    def jwt_secret(self) -> str:
        return _required("JWT_SECRET")

    @property
    def demo_customer_password(self) -> str | None:
        return os.getenv("DEMO_CUSTOMER_PASSWORD") or None

    @property
    def demo_internal_password(self) -> str | None:
        return os.getenv("DEMO_INTERNAL_PASSWORD") or None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES") or "60"),
        model_seed=int(os.getenv("SIM_SEED") or "42"),
        defect_rate=float(os.getenv("DEFECT_RATE") or "0.02"),
        tariffs_csv=os.getenv("TARIFFS_CSV") or "data/reference/tariffs.csv",
        f5_url=os.getenv("F5_URL") or "http://localhost:8005",
    )
