"""Modelos ORM del inventario de red (F4). Ver docs/erd.md."""

import datetime as dt
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Circuit(Base):
    __tablename__ = "circuit"
    __table_args__ = (
        CheckConstraint("capacity_kva > 0", name="capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    capacity_kva: Mapped[Decimal] = mapped_column(Numeric(8, 2))

    transformers: Mapped[list["Transformer"]] = relationship(back_populates="circuit")

class Transformer(Base):
    __tablename__ = "transformer"
    __table_args__ = (
        CheckConstraint("capacity_kva > 0", name="capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    circuit_id: Mapped[int] = mapped_column(ForeignKey("circuit.id"), index=True)
    capacity_kva: Mapped[Decimal] = mapped_column(Numeric(8, 2))

    meters: Mapped[list["Meter"]] = relationship(back_populates="transformer")
    circuit: Mapped["Circuit"] = relationship(back_populates="transformers")

class Customer(Base):
    __tablename__ = "customer"
    __table_args__ = (
        CheckConstraint(
            "acorn_grouped IN ('Affluent', 'Comfortable', 'Adversity', 'Unknown')",
            name="acorn_grouped_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    acorn_group: Mapped[str] = mapped_column(String(30))
    acorn_grouped: Mapped[str] = mapped_column(String(20))

    meters: Mapped[list["Meter"]] = relationship(back_populates="customer")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="customer")

class Contract(Base):
    __tablename__ = "contract"
    __table_args__ = (
        CheckConstraint("tariff_type IN ('standard', 'dynamic')", name="tariff_type_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    tariff_type: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)

    customer: Mapped["Customer"] = relationship(back_populates="contracts")

class Meter(Base):
    __tablename__ = "meter"

    id: Mapped[int] = mapped_column(primary_key=True)
    lclid: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    transformer_id: Mapped[int] = mapped_column(ForeignKey("transformer.id"), index=True)

    transformer: Mapped["Transformer"] = relationship(back_populates="meters")
    customer: Mapped["Customer"] = relationship(back_populates="meters")