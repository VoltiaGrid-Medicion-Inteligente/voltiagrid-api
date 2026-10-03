"""Seed CLI: network topology + F1 households."""

import argparse
import random
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from seed.config import VALID_MODES, SeedSettings, build_settings
from seed.f1 import (
    read_households,
    select_households,
    build_customer,
    build_contract,
    build_meter,
)
from seed.network import plan_network, NetworkPlan
from app.models.inventory import Circuit, Transformer, Customer, Contract, Meter


DEFAULT_HOUSEHOLDS_CSV = Path("data/raw/informations_households.csv")


def build_parser():
    parser = argparse.ArgumentParser(description="Seed del inventario de red (F4)")
    parser.add_argument("--seed", type=int, default=None, help="semilla fija")
    parser.add_argument("--mode", choices=VALID_MODES, default=None, help="dev o full")
    parser.add_argument("--defect-rate", type=float, default=None, help="tasa de defectos, de 0 a 1")
    parser.add_argument("--database-url", default=None, help="URL de la base de datos")
    return parser


def _rng_from_seed(seed: int) -> random.Random:
    """Create isolated RNG instance for deterministic seeding."""
    return random.Random(seed)


def seed_network_topology(rng: random.Random, lclids: list[str]) -> NetworkPlan:
    """Plan and return network topology (circuits, transformers, meter→transformer map)."""
    return plan_network(rng, lclids)


def seed_f1_households(rows: list[dict], meter_to_tx: dict[str, str]) -> tuple[list, list, list]:
    """Build customers, contracts, meters from household rows."""
    customers = []
    contracts = []
    meters = []

    for row in rows:
        customers.append(build_customer(row))
        contracts.append(build_contract(row))
        tx_code = meter_to_tx.get(row["LCLid"])
        meters.append(build_meter(row, transformer_code=tx_code))

    return customers, contracts, meters


def upsert_circuits(session: Session, circuits: list[dict]):
    if not circuits:
        return
    stmt = pg_insert(Circuit).values(circuits)
    stmt = stmt.on_conflict_do_nothing(index_elements=["code"])
    session.execute(stmt)


def _resolve_transformer_fks(session: Session, transformers: list[dict]) -> list[dict]:
    """Replace circuit_code with circuit_id."""
    circuit_codes = {t["circuit_code"] for t in transformers if t.get("circuit_code")}
    circuit_map = {}
    if circuit_codes:
        rows = session.query(Circuit.code, Circuit.id).filter(Circuit.code.in_(circuit_codes)).all()
        circuit_map = {code: id_ for code, id_ in rows}

    resolved = []
    for t in transformers:
        resolved_t = {k: v for k, v in t.items() if k != "circuit_code"}
        if t.get("circuit_code"):
            resolved_t["circuit_id"] = circuit_map.get(t["circuit_code"])
        resolved.append(resolved_t)
    return resolved


def upsert_transformers(session: Session, transformers: list[dict]):
    if not transformers:
        return
    transformers_resolved = _resolve_transformer_fks(session, transformers)
    stmt = pg_insert(Transformer).values(transformers_resolved)
    stmt = stmt.on_conflict_do_nothing(index_elements=["code"])
    session.execute(stmt)


def upsert_customers(session: Session, customers: list[dict]):
    if not customers:
        return
    stmt = pg_insert(Customer).values(customers)
    stmt = stmt.on_conflict_do_nothing(index_elements=["code"])
    session.execute(stmt)


def _resolve_contract_fks(session: Session, contracts: list[dict]) -> list[dict]:
    """Replace customer_code with customer_id."""
    cust_codes = {c["customer_code"] for c in contracts if c.get("customer_code")}
    cust_map = {}
    if cust_codes:
        rows = session.query(Customer.code, Customer.id).filter(Customer.code.in_(cust_codes)).all()
        cust_map = {code: id_ for code, id_ in rows}

    resolved = []
    for c in contracts:
        resolved_c = {k: v for k, v in c.items() if k != "customer_code"}
        if c.get("customer_code"):
            resolved_c["customer_id"] = cust_map.get(c["customer_code"])
        resolved.append(resolved_c)
    return resolved


def upsert_contracts(session: Session, contracts: list[dict]):
    if not contracts:
        return
    contracts_resolved = _resolve_contract_fks(session, contracts)
    stmt = pg_insert(Contract).values(contracts_resolved)
    stmt = stmt.on_conflict_do_nothing(index_elements=["code"])
    session.execute(stmt)


def upsert_meters(session: Session, meters: list[dict]):
    if not meters:
        return
    # Need to resolve transformer_code -> transformer_id, customer_code -> customer_id
    # For upsert, we'll do a two-pass: first ensure FKs exist, then upsert meters
    # Simpler: resolve codes to IDs before upsert
    pass  # Will handle in main()


def _resolve_fks(session: Session, meters: list[dict]) -> list[dict]:
    """Replace transformer_code/customer_code with transformer_id/customer_id."""
    # Build lookup maps
    tx_codes = {m["transformer_code"] for m in meters if m.get("transformer_code")}
    cust_codes = {m["customer_code"] for m in meters}

    tx_map = {}
    if tx_codes:
        rows = session.query(Transformer.code, Transformer.id).filter(Transformer.code.in_(tx_codes)).all()
        tx_map = {code: id_ for code, id_ in rows}

    cust_map = {}
    if cust_codes:
        rows = session.query(Customer.code, Customer.id).filter(Customer.code.in_(cust_codes)).all()
        cust_map = {code: id_ for code, id_ in rows}

    resolved = []
    for m in meters:
        resolved_m = {"lclid": m["lclid"]}
        if m.get("transformer_code"):
            resolved_m["transformer_id"] = tx_map.get(m["transformer_code"])
        if m.get("customer_code"):
            resolved_m["customer_id"] = cust_map.get(m["customer_code"])
        resolved.append(resolved_m)
    return resolved


def upsert_meters_resolved(session: Session, meters: list[dict]):
    if not meters:
        return
    stmt = pg_insert(Meter).values(meters)
    stmt = stmt.on_conflict_do_update(
        index_elements=["lclid"],
        set_={
            "transformer_id": stmt.excluded.transformer_id,
            "customer_id": stmt.excluded.customer_id,
        },
    )
    session.execute(stmt)


def main():
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = build_settings(args)
    except ValueError as error:
        parser.error(str(error))

    safe_url = str(settings.database_url)
    if "@" in safe_url:
        # Hide password in URL
        from sqlalchemy.engine import make_url
        safe_url = make_url(settings.database_url).render_as_string(hide_password=True)

    print("Configuración del seed")
    print(f"  seed:         {settings.seed}")
    print(f"  mode:         {settings.mode} ({settings.meter_count} medidores)")
    print(f"  defect_rate:  {settings.defect_rate}")
    print(f"  database_url: {safe_url}")

    # Create isolated RNG for deterministic results
    rng = _rng_from_seed(settings.seed)

    # 1. Read and select households (already sorted by LCLid in select_households)
    all_rows = read_households()
    selected_rows = select_households(all_rows, settings.meter_count)
    lclids = [row["LCLid"] for row in selected_rows]

    # 2. Plan network topology
    print("\nPlanificando topología de red...")
    plan = seed_network_topology(rng, lclids)
    print(f"  Circuitos: {len(plan.circuits)}")
    print(f"  Transformadores: {len(plan.transformers)}")
    print(f"  Medidores asignados: {len(plan.meter_to_transformer)}")

    # 3. Build F1 households
    print("\nConstruyendo hogares F1...")
    customers, contracts, meters = seed_f1_households(selected_rows, plan.meter_to_transformer)
    print(f"  Clientes: {len(customers)}")
    print(f"  Contratos: {len(contracts)}")
    print(f"  Medidores: {len(meters)}")

    # 4. Database upserts
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        print("\nInsertando en base de datos...")

        # Circuits & Transformers first (FK targets)
        upsert_circuits(session, plan.circuits)
        upsert_transformers(session, plan.transformers)
        session.flush()
        print(f"  Circuitos: OK")
        print(f"  Transformadores: OK")

        # Customers & Contracts
        upsert_customers(session, customers)
        upsert_contracts(session, contracts)
        session.flush()
        print(f"  Clientes: OK")
        print(f"  Contratos: OK")

        # Meters (resolve FKs then upsert)
        meters_resolved = _resolve_fks(session, meters)
        upsert_meters_resolved(session, meters_resolved)
        print(f"  Medidores: OK")

        session.commit()
        print("\n¡Seed completado con éxito!")


if __name__ == "__main__":
    main()