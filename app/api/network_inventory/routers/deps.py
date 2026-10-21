"""Dependencies shared by the inventory routers."""

from typing import Annotated

from fastapi import Depends, Query

from app.api.common import Principal, require_internal
from app.api.network_inventory.service import InventoryService, get_inventory_service

Internal = Annotated[Principal, Depends(require_internal)]
Service = Annotated[InventoryService, Depends(get_inventory_service)]
PageQuery = Annotated[int, Query(ge=1, description="Page number, from 1")]
SizeQuery = Annotated[int, Query(ge=1, le=200, description="Items per page, max 200")]
