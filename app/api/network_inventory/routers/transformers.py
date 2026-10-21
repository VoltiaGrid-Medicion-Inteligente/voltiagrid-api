"""Transformers of F4 (US-18, T-18.3)."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.common import AUTH_ERRORS, CONFLICT, NOT_FOUND, VALIDATION, Page
from app.api.network_inventory.routers.deps import Internal, PageQuery, Service, SizeQuery
from app.api.network_inventory.schemas import CapacityUpdate, TransformerIn, TransformerOut

router = APIRouter(prefix="/transformers", tags=["transformers"])
Code = Annotated[str, Path(examples=["TR-00000"])]


@router.post("", response_model=TransformerOut, status_code=201,
             responses={**AUTH_ERRORS, **NOT_FOUND, **CONFLICT, **VALIDATION})
def create_transformer(body: TransformerIn, service: Service, _: Internal):
    return service.create_transformer(body)


@router.get("", response_model=Page[TransformerOut], responses={**AUTH_ERRORS, **VALIDATION})
def list_transformers(service: Service, _: Internal, page: PageQuery = 1, size: SizeQuery = 50,
                      circuit_code: Annotated[str | None, Query(examples=["CT-000"])] = None):
    return service.list_transformers(page, size, circuit_code)


@router.get("/{code}", response_model=TransformerOut, responses={**AUTH_ERRORS, **NOT_FOUND})
def get_transformer(code: Code, service: Service, _: Internal):
    return service.get_transformer(code)


@router.patch("/{code}", response_model=TransformerOut, responses={**AUTH_ERRORS, **NOT_FOUND, **VALIDATION})
def update_transformer_capacity(code: Code, body: CapacityUpdate, service: Service, _: Internal):
    return service.update_transformer_capacity(code, body.capacity_kva)
