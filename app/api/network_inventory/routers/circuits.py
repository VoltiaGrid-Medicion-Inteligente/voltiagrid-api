"""Circuits of F4 (US-18, T-18.3)."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.common import AUTH_ERRORS, CONFLICT, NOT_FOUND, VALIDATION, Page
from app.api.network_inventory.routers.deps import Internal, PageQuery, Service, SizeQuery
from app.api.network_inventory.schemas import CapacityUpdate, CircuitIn, CircuitOut

router = APIRouter(prefix="/circuits", tags=["circuits"])
Code = Annotated[str, Path(examples=["CT-000"])]


@router.post("", response_model=CircuitOut, status_code=201, responses={**AUTH_ERRORS, **CONFLICT, **VALIDATION})
def create_circuit(body: CircuitIn, service: Service, _: Internal):
    return service.create_circuit(body)


@router.get("", response_model=Page[CircuitOut], responses={**AUTH_ERRORS, **VALIDATION})
def list_circuits(service: Service, _: Internal, page: PageQuery = 1, size: SizeQuery = 50):
    return service.list_circuits(page, size)


@router.get("/{code}", response_model=CircuitOut, responses={**AUTH_ERRORS, **NOT_FOUND})
def get_circuit(code: Code, service: Service, _: Internal):
    return service.get_circuit(code)


@router.patch("/{code}", response_model=CircuitOut, responses={**AUTH_ERRORS, **NOT_FOUND, **VALIDATION})
def update_circuit_capacity(code: Code, body: CapacityUpdate, service: Service, _: Internal):
    return service.update_circuit_capacity(code, body.capacity_kva)
