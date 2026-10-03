# seed/upsert.py
"""Reusable upsert-by-natural-key utilities."""

from typing import Callable, Optional
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


def upsert_by_natural_key(
    session: Session,
    model,
    records: list[dict],
    natural_key: str,
    update_fields: Optional[list[str]] = None,
    fk_resolver: Optional[Callable[[Session, list[dict]], list[dict]]] = None,
):
    """
    Upsert records by natural key (unique column).
    
    Args:
        session: SQLAlchemy session
        model: ORM model class
        records: List of dicts with column values
        natural_key: Name of unique column (e.g., "code", "lclid")
        update_fields: If set, ON CONFLICT DO UPDATE these fields; else DO NOTHING
        fk_resolver: Optional function(session, records) -> resolved_records
                     to convert FK codes to IDs before upsert
    """
    if not records:
        return

    # Resolve FKs if resolver provided
    if fk_resolver:
        records = fk_resolver(session, records)

    stmt = pg_insert(model).values(records)
    
    if update_fields:
        stmt = stmt.on_conflict_do_update(
            index_elements=[natural_key],
            set_={f: getattr(stmt.excluded, f) for f in update_fields},
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=[natural_key])
    
    session.execute(stmt)