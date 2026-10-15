"""F5 transformer metering API (US-15).

    uvicorn simulators.transformer_api.main:app --port 8005
    open http://localhost:8005/docs

Endpoints:
    GET    /health
    GET    /transformers                                   codes and meter count
    GET    /transformers/{code}/energy?start=...&end=...   delivered kWh every 15 minutes
    POST   /losses                                         inject a loss in a period (T-15.2)
    GET    /losses
    DELETE /losses/{id}
"""

import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, Field, model_validator

from simulators.common.inventory import Inventory, load_from_db, with_volume
from simulators.transformer_api.losses import LossStore
from simulators.transformer_api.service import delivered_series

MAX_RANGE = timedelta(days=7)

app = FastAPI(
    title="VoltiaGrid transformer metering API (F5)",
    version="1.0.0",
    description="Simulated energy delivered per transformer every 15 minutes, with loss injection.",
)


# ---------- dependencies (replaced in tests) ----------

def get_seed() -> int:
    return int(os.getenv("SIM_SEED") or os.getenv("SEED") or "42")


@lru_cache(maxsize=1)
def get_inventory() -> Inventory:
    synthetic = int(os.getenv("SIM_SYNTHETIC_METERS") or "0")
    if synthetic:
        return with_volume(Inventory({}), synthetic)
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing (or set SIM_SYNTHETIC_METERS)")
    return load_from_db(url)


_store = LossStore()


def get_loss_store() -> LossStore:
    return _store


InventoryDep = Annotated[Inventory, Depends(get_inventory)]
StoreDep = Annotated[LossStore, Depends(get_loss_store)]
SeedDep = Annotated[int, Depends(get_seed)]


# ---------- schemas ----------

class EnergyReading(BaseModel):
    interval_start: datetime
    delivered_kwh: float


class EnergyResponse(BaseModel):
    transformer_code: str
    interval_minutes: int = 15
    readings: list[EnergyReading]


class TransformerOut(BaseModel):
    transformer_code: str
    meters: int


class LossIn(BaseModel):
    transformer_code: str = Field(examples=["TR-00001"])
    start: AwareDatetime = Field(examples=["2013-01-01T00:00:00Z"])
    end: AwareDatetime = Field(examples=["2013-01-04T00:00:00Z"])
    loss_pct: float = Field(gt=0, le=1, description="0.15 = 15% more energy delivered than metered")

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class LossOut(LossIn):
    id: int


# ---------- endpoints ----------

def _require_transformer(inventory: Inventory, code: str) -> None:
    if not inventory.meters_of(code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Transformer '{code}' not found")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/transformers", response_model=list[TransformerOut])
def list_transformers(inventory: InventoryDep):
    return [
        TransformerOut(transformer_code=code, meters=len(meters))
        for code, meters in sorted(inventory.meters_by_transformer.items())
    ]


@app.get("/transformers/{code}/energy", response_model=EnergyResponse)
def transformer_energy(
    code: str,
    inventory: InventoryDep,
    store: StoreDep,
    seed: SeedDep,
    start: Annotated[AwareDatetime, Query(description="ISO 8601 with time zone, e.g. 2013-01-01T00:00:00Z")],
    end: Annotated[AwareDatetime, Query(description="exclusive")],
):
    _require_transformer(inventory, code)
    if end <= start:
        raise HTTPException(422, "end must be after start")
    if end - start > MAX_RANGE:
        raise HTTPException(422, "range must be 7 days or less")
    rows = delivered_series(inventory, store, code, start, end, seed)
    return EnergyResponse(transformer_code=code, readings=[EnergyReading(**r) for r in rows])


@app.post("/losses", response_model=LossOut, status_code=status.HTTP_201_CREATED)
def inject_loss(body: LossIn, inventory: InventoryDep, store: StoreDep):
    _require_transformer(inventory, body.transformer_code)
    item = store.add(body.transformer_code, body.start, body.end, body.loss_pct)
    return LossOut(**item.__dict__)


@app.get("/losses", response_model=list[LossOut])
def list_losses(store: StoreDep):
    return [LossOut(**i.__dict__) for i in store.all()]


@app.delete("/losses/{injection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loss(injection_id: int, store: StoreDep):
    if not store.remove(injection_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Loss injection {injection_id} not found")