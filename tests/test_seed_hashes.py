"""Inventory fingerprint used to compare local and RDS data (US-25, T-25.3)."""

import datetime as dt
from decimal import Decimal

from app.models.inventory import Circuit, Contract, Customer, Meter, Transformer
from seed.hashes import QUERIES, fingerprint, render, total


def test_every_f4_table_is_fingerprinted():
    assert list(QUERIES) == ["circuit", "transformer", "customer", "contract", "meter"]


def test_total_changes_when_any_table_changes():
    a = {t: (1, "0" * 32) for t in QUERIES}
    b = {**a, "meter": (1, "f" * 32)}
    assert total(a) != total(b)
    assert total(a) == total(dict(reversed(list(a.items()))))


def test_render_has_one_line_per_table_and_a_total():
    lines = render({t: (3, "a" * 32) for t in QUERIES}).splitlines()
    assert len(lines) == 6
    assert lines[0].startswith("circuit") and "3 rows" in lines[0]
    assert lines[-1].startswith("TOTAL")


def _load(session, order):
    """Inserts the same small network, creating circuits in the given order (so ids differ)."""
    circuits = {code: Circuit(code=code, capacity_kva=Decimal("1500.00")) for code in order}
    session.add_all(circuits.values())
    session.flush()
    customer = Customer(code="CU-HASH01", acorn_group="ACORN-A", acorn_grouped="Affluent")
    transformer = Transformer(code="TR-HASH01", circuit=circuits["CT-HASH1"], capacity_kva=Decimal("141.00"))
    session.add_all([customer, transformer])
    session.flush()
    session.add_all([
        Contract(code="CT-HASH01-1", customer_id=customer.id, tariff_type="standard",
                 start_date=dt.date(2013, 1, 1), end_date=None),
        Meter(lclid="HASH01", customer_id=customer.id, transformer_id=transformer.id),
    ])
    session.flush()


def test_same_data_with_different_ids_gives_the_same_fingerprint(session):
    first = session.begin_nested()
    _load(session, ["CT-HASH1", "CT-HASH2"])
    a = fingerprint(session.connection())
    first.rollback()

    second = session.begin_nested()
    session.add(Circuit(code="CT-HASH0", capacity_kva=Decimal("1.00")))  # burns an id
    session.flush()
    session.query(Circuit).filter_by(code="CT-HASH0").delete()
    _load(session, ["CT-HASH2", "CT-HASH1"])
    b = fingerprint(session.connection())
    second.rollback()

    assert a == b


def test_a_changed_capacity_changes_the_fingerprint(session):
    _load(session, ["CT-HASH1", "CT-HASH2"])
    before = fingerprint(session.connection())
    session.query(Transformer).filter_by(code="TR-HASH01").update({"capacity_kva": Decimal("142.00")})
    session.flush()
    after = fingerprint(session.connection())
    assert before["transformer"] != after["transformer"]
    assert before["meter"] == after["meter"]
