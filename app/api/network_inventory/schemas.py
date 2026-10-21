"""Request and response schemas of the network inventory API (US-18, T-18.1).

Same fields, lengths and allowed values as the F4 models (app/models/inventory.py
and the operational dictionary). Every resource is identified by its natural
key; an invalid body returns 422 naming the field that failed.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

AcornGrouped = Literal["Affluent", "Comfortable", "Adversity", "Unknown"]

CustomerCode = Annotated[str, Field(min_length=4, max_length=30, pattern=r"^CU-[A-Z0-9]+$", examples=["CU-MAC009999"])]
CircuitCode = Annotated[str, Field(min_length=4, max_length=20, pattern=r"^CT-[A-Z0-9]+$", examples=["CT-001"])]
TransformerCode = Annotated[str, Field(min_length=4, max_length=20, pattern=r"^TR-[A-Z0-9]+$", examples=["TR-00099"])]
Lclid = Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9]+$", examples=["MAC009999"])]
Capacity = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2, examples=["250.00"],
                                    description="kVA, up to 6 digits and 2 decimals (NUMERIC(8,2))")]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CustomerIn(_In):
    code: CustomerCode
    acorn_group: str = Field(min_length=1, max_length=30, examples=["ACORN-E"])
    acorn_grouped: AcornGrouped


class CustomerOut(BaseModel):
    code: str = Field(examples=["CU-MAC000002"])
    acorn_group: str = Field(examples=["ACORN-A"])
    acorn_grouped: AcornGrouped


class CircuitIn(_In):
    code: CircuitCode
    capacity_kva: Capacity


class CircuitOut(BaseModel):
    code: str = Field(examples=["CT-000"])
    capacity_kva: Decimal = Field(examples=["2100.12"])
    transformers: int = Field(description="number of transformers in the circuit", examples=[7])


class TransformerIn(_In):
    code: TransformerCode
    circuit_code: CircuitCode
    capacity_kva: Capacity


class TransformerOut(BaseModel):
    code: str = Field(examples=["TR-00001"])
    circuit_code: str = Field(examples=["CT-000"])
    capacity_kva: Decimal = Field(examples=["141.00"])
    meters: int = Field(description="number of meters connected", examples=[64])


class CapacityUpdate(_In):
    capacity_kva: Capacity


class MeterIn(_In):
    lclid: Lclid
    customer_code: CustomerCode
    transformer_code: TransformerCode


class MeterOut(BaseModel):
    lclid: str = Field(examples=["MAC000002"])
    customer_code: str = Field(examples=["CU-MAC000002"])
    transformer_code: str = Field(examples=["TR-00000"])
