"""US-18 (T-18.2): the inventory service works on the F4 ORM through the repository."""

from decimal import Decimal

import pytest

from app.api.network_inventory.repository import InventoryRepository
from app.api.network_inventory.schemas import CircuitIn, CustomerIn, MeterIn, TransformerIn
from app.api.network_inventory.service import InventoryService
from app.core.errors import ConflictError, NotFoundError


@pytest.fixture
def service(session):
    return InventoryService(InventoryRepository(session))


@pytest.fixture
def network(service):
    service.create_circuit(CircuitIn(code="CT-SVC1", capacity_kva="1500.00"))
    service.create_transformer(TransformerIn(code="TR-SVC01", circuit_code="CT-SVC1", capacity_kva="200.00"))
    service.create_customer(CustomerIn(code="CU-SVC0001", acorn_group="ACORN-A", acorn_grouped="Affluent"))
    service.create_meter(MeterIn(lclid="SVC0001", customer_code="CU-SVC0001", transformer_code="TR-SVC01"))
    return service


def test_create_and_read_back_with_counts(network):
    assert network.get_circuit("CT-SVC1").transformers == 1
    transformer = network.get_transformer("TR-SVC01")
    assert transformer.circuit_code == "CT-SVC1" and transformer.meters == 1
    assert network.get_meter("SVC0001").customer_code == "CU-SVC0001"


def test_duplicate_natural_key_is_a_conflict(network):
    with pytest.raises(ConflictError):
        network.create_customer(CustomerIn(code="CU-SVC0001", acorn_group="ACORN-A", acorn_grouped="Affluent"))


def test_references_must_exist(network):
    with pytest.raises(NotFoundError, match="Circuit 'CT-NOPE'"):
        network.create_transformer(TransformerIn(code="TR-SVC02", circuit_code="CT-NOPE", capacity_kva="100"))
    with pytest.raises(NotFoundError, match="Customer 'CU-NOPE'"):
        network.create_meter(MeterIn(lclid="SVC0002", customer_code="CU-NOPE", transformer_code="TR-SVC01"))


def test_unknown_code_is_not_found(service):
    with pytest.raises(NotFoundError):
        service.get_transformer("TR-NOPE")


def test_capacity_update(network):
    assert network.update_transformer_capacity("TR-SVC01", Decimal("250.50")).capacity_kva == Decimal("250.50")


def test_filters_and_pagination(network):
    network.create_meter(MeterIn(lclid="SVC0002", customer_code="CU-SVC0001", transformer_code="TR-SVC01"))
    page = network.list_meters(page=1, size=1, transformer_code="TR-SVC01")
    assert page["total"] == 2 and len(page["items"]) == 1
    second = network.list_meters(page=2, size=1, transformer_code="TR-SVC01")
    assert second["items"][0].lclid != page["items"][0].lclid
