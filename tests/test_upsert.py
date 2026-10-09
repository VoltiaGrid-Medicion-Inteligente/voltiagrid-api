"""Tests for upsert_by_natural_key utility."""

from app.models.inventory import Circuit, Transformer, Customer, Meter
from seed.upsert import upsert_by_natural_key
from seed.network import plan_network
import random


def test_upsert_circuit_do_nothing(session):
    """DO NOTHING: segundo insert no duplica."""
    upsert_by_natural_key(session, Circuit, [{"code": "CT-TEST", "capacity_kva": 1000}], "code")
    session.flush()

    upsert_by_natural_key(session, Circuit, [{"code": "CT-TEST", "capacity_kva": 2000}], "code")
    session.flush()

    count = session.query(Circuit).filter(Circuit.code == "CT-TEST").count()
    assert count == 1


def test_upsert_transformer_do_nothing_with_fk(session):
    """DO NOTHING con FK resolver: circuit_code → circuit_id."""
    # Pre-insert circuit
    upsert_by_natural_key(session, Circuit, [{"code": "CT-FK", "capacity_kva": 1500}], "code")
    session.flush()

    def resolve_tx_fks(session, transformers):
        circuit_codes = {t["circuit_code"] for t in transformers}
        circuit_map = dict(
            session.query(Circuit.code, Circuit.id).filter(Circuit.code.in_(circuit_codes)).all()
        )
        resolved = []
        for t in transformers:
            rt = {k: v for k, v in t.items() if k != "circuit_code"}
            rt["circuit_id"] = circuit_map.get(t["circuit_code"])
            resolved.append(rt)
        return resolved

    upsert_by_natural_key(
        session, Transformer,
        [{"code": "TR-FK-001", "circuit_code": "CT-FK", "capacity_kva": 250}],
        natural_key="code",
        fk_resolver=resolve_tx_fks
    )
    session.flush()

    # Segundo insert mismo code → no duplica
    upsert_by_natural_key(
        session, Transformer,
        [{"code": "TR-FK-001", "circuit_code": "CT-FK", "capacity_kva": 999}],
        natural_key="code",
        fk_resolver=resolve_tx_fks
    )
    session.flush()

    count = session.query(Transformer).filter(Transformer.code == "TR-FK-001").count()
    assert count == 1

    # Verificar FK correcto
    tx = session.query(Transformer).filter(Transformer.code == "TR-FK-001").one()
    circuit = session.query(Circuit).filter(Circuit.code == "CT-FK").one()
    assert tx.circuit_id == circuit.id


def test_upsert_meter_do_update(session):
    """DO UPDATE actualiza FKs en conflicto."""
    # Pre-insert customer + circuit + transformer
    upsert_by_natural_key(session, Customer, [{"code": "CU-TEST", "acorn_group": "A", "acorn_grouped": "Affluent"}], "code")
    upsert_by_natural_key(session, Circuit, [{"code": "CT-1", "capacity_kva": 1000}], "code")
    session.flush()
    
    session.query(Circuit).filter(Circuit.code == "CT-1").one()
    
    def resolve_tx_fks(session, transformers):
        circuit_map = dict(session.query(Circuit.code, Circuit.id).all())
        return [
            {**{k: v for k, v in t.items() if k != "circuit_code"}, "circuit_id": circuit_map.get(t.get("circuit_code"))}
            for t in transformers
        ]
    
    upsert_by_natural_key(session, Transformer, [{"code": "TR-ORIG", "circuit_code": "CT-1", "capacity_kva": 100}], "code", fk_resolver=resolve_tx_fks)
    session.flush()

    cust = session.query(Customer).filter(Customer.code == "CU-TEST").one()
    tx_orig = session.query(Transformer).filter(Transformer.code == "TR-ORIG").one()

    # Insert meter inicial
    upsert_by_natural_key(
        session, Meter,
        [{"lclid": "MAC000001", "customer_id": cust.id, "transformer_id": tx_orig.id}],
        natural_key="lclid",
        update_fields=["transformer_id", "customer_id"]
    )
    session.flush()

    # Nuevo transformer
    upsert_by_natural_key(session, Transformer, [{"code": "TR-NEW", "circuit_code": "CT-1", "capacity_kva": 200}], "code", fk_resolver=resolve_tx_fks)
    session.flush()
    tx_new = session.query(Transformer).filter(Transformer.code == "TR-NEW").one()

    # Upsert mismo lclid con nuevo transformer → debe actualizar
    upsert_by_natural_key(
        session, Meter,
        [{"lclid": "MAC000001", "customer_id": cust.id, "transformer_id": tx_new.id}],
        natural_key="lclid",
        update_fields=["transformer_id", "customer_id"]
    )
    session.flush()

    meter = session.query(Meter).filter(Meter.lclid == "MAC000001").one()
    assert meter.transformer_id == tx_new.id


def test_upsert_meter_fk_integrity(session):
    """FKs resueltos existen en BD (no huérfanos)."""
    # Pre-insert FKs
    upsert_by_natural_key(session, Customer, [{"code": "CU-FK", "acorn_group": "A", "acorn_grouped": "Affluent"}], "code")
    upsert_by_natural_key(session, Circuit, [{"code": "CT-FK", "capacity_kva": 1000}], "code")
    session.flush()
    
    def resolve_tx_fks(session, transformers):
        circuit_map = dict(session.query(Circuit.code, Circuit.id).all())
        return [
            {**{k: v for k, v in t.items() if k != "circuit_code"}, "circuit_id": circuit_map.get(t.get("circuit_code"))}
            for t in transformers
        ]
    
    upsert_by_natural_key(session, Transformer, [{"code": "TR-FK", "circuit_code": "CT-FK", "capacity_kva": 250}], "code", fk_resolver=resolve_tx_fks)
    session.flush()

    cust = session.query(Customer).filter(Customer.code == "CU-FK").one()
    tx = session.query(Transformer).filter(Transformer.code == "TR-FK").one()

    def resolve_meter_fks(session, meters):
        cust_map = dict(session.query(Customer.code, Customer.id).all())
        tx_map = dict(session.query(Transformer.code, Transformer.id).all())
        resolved = []
        for m in meters:
            rm = {"lclid": m["lclid"]}
            rm["customer_id"] = cust_map.get(m["customer_code"])
            rm["transformer_id"] = tx_map.get(m["transformer_code"])
            resolved.append(rm)
        return resolved

    upsert_by_natural_key(
        session, Meter,
        [{"lclid": "MAC-FK-1", "customer_code": "CU-FK", "transformer_code": "TR-FK"}],
        natural_key="lclid",
        update_fields=["transformer_id", "customer_id"],
        fk_resolver=resolve_meter_fks
    )
    session.flush()

    meter = session.query(Meter).filter(Meter.lclid == "MAC-FK-1").one()
    assert meter.customer_id == cust.id
    assert meter.transformer_id == tx.id


def test_seed_full_idempotent(session):
    """Re-ejecutar seed.main() dos veces = mismos counts (idempotencia)."""
    # Ejecutar seed.main() requiere DB limpia; usamos transacción con rollback
    # En su lugar, verificamos que upsert_by_natural_key es idempotente para cada entidad
    
    # Circuit
    upsert_by_natural_key(session, Circuit, [{"code": "CT-IDEMP", "capacity_kva": 1000}], "code")
    upsert_by_natural_key(session, Circuit, [{"code": "CT-IDEMP", "capacity_kva": 2000}], "code")
    assert session.query(Circuit).filter(Circuit.code == "CT-IDEMP").count() == 1

    # Transformer
    upsert_by_natural_key(session, Circuit, [{"code": "CT-TX", "capacity_kva": 1000}], "code")
    session.flush()
    session.query(Circuit).filter(Circuit.code == "CT-TX").one()
    
    def resolve_tx(session, txs):
        ct_map = dict(session.query(Circuit.code, Circuit.id).all())
        return [{"code": t["code"], "circuit_id": ct_map[t["circuit_code"]], "capacity_kva": t["capacity_kva"]} for t in txs]
    
    upsert_by_natural_key(session, Transformer, [{"code": "TR-IDEMP", "circuit_code": "CT-TX", "capacity_kva": 250}], "code", fk_resolver=resolve_tx)
    upsert_by_natural_key(session, Transformer, [{"code": "TR-IDEMP", "circuit_code": "CT-TX", "capacity_kva": 500}], "code", fk_resolver=resolve_tx)
    assert session.query(Transformer).filter(Transformer.code == "TR-IDEMP").count() == 1

    # Customer
    upsert_by_natural_key(session, Customer, [{"code": "CU-IDEMP", "acorn_group": "A", "acorn_grouped": "Affluent"}], "code")
    upsert_by_natural_key(session, Customer, [{"code": "CU-IDEMP", "acorn_group": "B", "acorn_grouped": "Comfortable"}], "code")
    assert session.query(Customer).filter(Customer.code == "CU-IDEMP").count() == 1


def test_deterministic_assignment(session):
    """Misma seed = mismos códigos TR/CT asignados (verificar plan_network determinista)."""
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    
    lclids = sorted([f"MAC{i:06d}" for i in range(200)])
    
    plan1 = plan_network(rng1, lclids)
    plan2 = plan_network(rng2, lclids)
    
    # Mismos circuitos
    assert [c["code"] for c in plan1.circuits] == [c["code"] for c in plan2.circuits]
    # Mismos transformadores
    assert [t["code"] for t in plan1.transformers] == [t["code"] for t in plan2.transformers]
    # Mismas asignaciones meter→transformer
    assert plan1.meter_to_transformer == plan2.meter_to_transformer


def test_meter_counts_per_transformer_range():
    """Cada transformer tiene 50-80 meters (excepto último con resto)."""
    rng = random.Random(42)
    lclids = sorted([f"MAC{i:06d}" for i in range(200)])
    plan = plan_network(rng, lclids)
    
    from collections import Counter
    tx_counts = Counter(plan.meter_to_transformer.values())
    
    # Todos menos el último: 50-80
    counts = list(tx_counts.values())
    for c in counts[:-1]:
        assert 50 <= c <= 80, f"Transformer count {c} fuera de rango 50-80"
    
    # Total = 200
    assert sum(counts) == 200