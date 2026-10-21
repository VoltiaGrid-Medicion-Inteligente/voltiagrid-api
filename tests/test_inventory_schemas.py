"""US-18 (T-18.1): request schemas validate like F4 and name the invalid field."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.network_inventory.schemas import CapacityUpdate, CircuitIn, CustomerIn, MeterIn, TransformerIn


def failed_fields(exc: ValidationError) -> set[str]:
    return {".".join(str(p) for p in e["loc"]) for e in exc.errors()}


def test_valid_bodies_are_accepted():
    CustomerIn(code="CU-MAC009999", acorn_group="ACORN-E", acorn_grouped="Affluent")
    CircuitIn(code="CT-001", capacity_kva="1500.50")
    TransformerIn(code="TR-00099", circuit_code="CT-001", capacity_kva=Decimal("250"))
    MeterIn(lclid="MAC009999", customer_code="CU-MAC009999", transformer_code="TR-00099")


@pytest.mark.parametrize("body,field", [
    ({"code": "MAC009999", "acorn_group": "ACORN-E", "acorn_grouped": "Affluent"}, "code"),
    ({"code": "CU-MAC009999", "acorn_group": "", "acorn_grouped": "Affluent"}, "acorn_group"),
    ({"code": "CU-MAC009999", "acorn_group": "ACORN-E", "acorn_grouped": "Rich"}, "acorn_grouped"),
    ({"code": "CU-" + "A" * 30, "acorn_group": "ACORN-E", "acorn_grouped": "Affluent"}, "code"),
])
def test_invalid_customer_names_the_field(body, field):
    with pytest.raises(ValidationError) as exc:
        CustomerIn(**body)
    assert field in failed_fields(exc.value)


@pytest.mark.parametrize("capacity", ["0", "-10", "1234567.00", "10.123"])
def test_capacity_must_fit_numeric_8_2_and_be_positive(capacity):
    with pytest.raises(ValidationError) as exc:
        CapacityUpdate(capacity_kva=capacity)
    assert "capacity_kva" in failed_fields(exc.value)


def test_transformer_needs_a_valid_circuit_code():
    with pytest.raises(ValidationError) as exc:
        TransformerIn(code="TR-00099", circuit_code="CIRCUIT-1", capacity_kva="100")
    assert failed_fields(exc.value) == {"circuit_code"}


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError) as exc:
        CircuitIn(code="CT-001", capacity_kva="100", owner="me")
    assert "owner" in failed_fields(exc.value)
