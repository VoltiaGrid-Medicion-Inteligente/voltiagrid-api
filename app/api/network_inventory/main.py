"""Network inventory API, F4 (US-18).

    uvicorn app.api.network_inventory.main:app --port 8003
    open http://localhost:8003/docs

Customers, circuits, transformers and meters of the F4 inventory, for internal
users. Resources are identified by their natural key (code or lclid), never by
the internal id. Layers: routers (HTTP) -> InventoryService (rules) ->
InventoryRepository (ORM). Every error has the same JSON format (app/core/errors.py).
"""

from fastapi import FastAPI

from app.api.common import Health
from app.api.network_inventory.routers import circuits, customers, meters, transformers
from app.core.config import get_settings
from app.core.errors import register_error_handlers

app = FastAPI(
    title="VoltiaGrid network inventory API",
    version="1.0.0",
    description="Customers, circuits, transformers and meters of the network inventory (F4).",
    root_path=get_settings().root_path,  # /inventory behind the load balancer (T-27.3)
)
register_error_handlers(app)

for module in (customers, circuits, transformers, meters):
    app.include_router(module.router)


@app.get("/health", response_model=Health, tags=["health"])
def health():
    return Health()
