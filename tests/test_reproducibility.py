"""Test de reproducibilidad CT-06: hash de tablas en dos corridas con misma seed."""

import os
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from seed.__main__ import main as seed_main
from app.models.inventory import Circuit, Transformer, Customer, Contract, Meter


def compute_table_hash(session: Session, model, natural_key: str) -> str:
    """Hash determinista de tabla ordenado por natural key."""
    cols = [c.name for c in model.__table__.columns]
    cols_sql = ", ".join(cols)
    query = f"""
        SELECT md5(string_agg(row_hash, '' ORDER BY {natural_key}))
        FROM (
            SELECT md5(concat_ws('|', {cols_sql})) as row_hash, {natural_key}
            FROM {model.__tablename__}
        ) t
    """
    result = session.execute(text(query)).scalar()
    return result or "empty"


def run_seed_and_get_engine(seed=42, mode="dev", defect_rate=0.0, database_url=None):
    """Ejecuta seed.main() y retorna el engine creado."""
    test_args = [
        "seed", "--seed", str(seed), "--mode", mode,
        "--defect-rate", str(defect_rate)
    ]
    if database_url:
        test_args.extend(["--database-url", database_url])

    # Capturar el engine creado por seed_main
    created_engine = {}
    
    original_create_engine = create_engine
    def tracking_create_engine(*args, **kwargs):
        eng = original_create_engine(*args, **kwargs)
        created_engine['engine'] = eng
        return eng
    
    with patch.object(sys, 'argv', test_args):
        with patch('seed.__main__.create_engine', tracking_create_engine):
            seed_main()
    
    return created_engine.get('engine')


def test_seed_reproducibility():
    """CT-06: Dos corridas con misma seed = tablas idénticas (hash)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL no configurada")
    
    settings_args = {
        "seed": 42,
        "mode": "dev",
        "defect_rate": 0.0,
        "database_url": database_url
    }

    # --- Primera corrida ---
    engine1 = run_seed_and_get_engine(**settings_args)
    assert engine1 is not None, "Seed no creó engine"
    
    with Session(engine1) as s1:
        hashes_1 = {
            "circuit": compute_table_hash(s1, Circuit, "code"),
            "transformer": compute_table_hash(s1, Transformer, "code"),
            "customer": compute_table_hash(s1, Customer, "code"),
            "contract": compute_table_hash(s1, Contract, "code"),
            "meter": compute_table_hash(s1, Meter, "lclid"),
        }

    # --- Segunda corrida (misma seed, defect_rate=0) ---
    engine2 = run_seed_and_get_engine(**settings_args)
    assert engine2 is not None, "Seed no creó engine"
    
    with Session(engine2) as s2:
        hashes_2 = {
            "circuit": compute_table_hash(s2, Circuit, "code"),
            "transformer": compute_table_hash(s2, Transformer, "code"),
            "customer": compute_table_hash(s2, Customer, "code"),
            "contract": compute_table_hash(s2, Contract, "code"),
            "meter": compute_table_hash(s2, Meter, "lclid"),
        }

    # --- Verificar ---
    for table in hashes_1:
        assert hashes_1[table] == hashes_2[table], (
            f"Hash mismatch en {table}: {hashes_1[table]} != {hashes_2[table]}"
        )