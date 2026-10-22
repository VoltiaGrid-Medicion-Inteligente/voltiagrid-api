"""F4 data the control center needs: transformers, their circuit and capacity (US-19)."""

from dataclasses import dataclass
from decimal import Decimal

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models.inventory import Circuit, Transformer


@dataclass(frozen=True)
class TransformerInfo:
    code: str
    circuit_code: str
    capacity_kva: Decimal


class ControlCenterRepository:
    def __init__(self, session: Session):
        self.session = session

    def _query(self):
        return (
            select(Transformer.code, Circuit.code.label("circuit_code"), Transformer.capacity_kva)
            .join(Circuit, Transformer.circuit_id == Circuit.id)
            .order_by(Transformer.code)
        )

    def get_transformer(self, code: str) -> TransformerInfo | None:
        row = self.session.execute(self._query().where(Transformer.code == code)).first()
        return TransformerInfo(*row) if row else None

    def list_transformers(self, circuit_code: str | None = None) -> list[TransformerInfo]:
        query = self._query()
        if circuit_code:
            query = query.where(Circuit.code == circuit_code)
        return [TransformerInfo(*row) for row in self.session.execute(query).all()]


def get_repository(session: Session = Depends(get_session)) -> ControlCenterRepository:
    return ControlCenterRepository(session)
