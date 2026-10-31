"""Fingerprint of the F4 inventory, to check that two databases hold the same data (US-25, T-25.3).

    python -m seed.hashes        # same connection settings as the seed: DATABASE_URL or DB_*

Prints one line per table with its row count and an md5 of every row in natural-key order, and a
total line. Internal ids are left out and every foreign key is replaced by the natural key it points to,
so a local database and RDS loaded with the same seed print the same lines even if their id sequences differ.
"""

import hashlib

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.core.database_url import require_database_url

# One text line per row; the first field is the natural key, so ordering by line = ordering by key.
QUERIES = {
    "circuit": """
        SELECT concat_ws('|', code, capacity_kva::text) FROM circuit
    """,
    "transformer": """
        SELECT concat_ws('|', t.code, c.code, t.capacity_kva::text)
        FROM transformer t JOIN circuit c ON c.id = t.circuit_id
    """,
    "customer": """
        SELECT concat_ws('|', code, acorn_group, acorn_grouped) FROM customer
    """,
    "contract": """
        SELECT concat_ws('|', k.code, cu.code, k.tariff_type, k.start_date::text, coalesce(k.end_date::text, ''))
        FROM contract k JOIN customer cu ON cu.id = k.customer_id
    """,
    "meter": """
        SELECT concat_ws('|', m.lclid, cu.code, t.code)
        FROM meter m
        JOIN customer cu ON cu.id = m.customer_id
        JOIN transformer t ON t.id = m.transformer_id
    """,
}


def fingerprint(connection) -> dict[str, tuple[int, str]]:
    """{table: (rows, md5)} for the five F4 tables."""
    result = {}
    for table, select in QUERIES.items():
        lines = sorted(row[0] for row in connection.execute(text(select)))
        digest = hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()
        result[table] = (len(lines), digest)
    return result


def total(prints: dict[str, tuple[int, str]]) -> str:
    joined = "\n".join(f"{table}:{rows}:{digest}" for table, (rows, digest) in sorted(prints.items()))
    return hashlib.md5(joined.encode("utf-8")).hexdigest()


def render(prints: dict[str, tuple[int, str]]) -> str:
    lines = [f"{table:<12} {rows:>6} rows  {digest}" for table, (rows, digest) in prints.items()]
    lines.append(f"{'TOTAL':<12} {'':>6}       {total(prints)}")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    engine = create_engine(require_database_url())
    with engine.connect() as connection:
        print(render(fingerprint(connection)))


if __name__ == "__main__":
    main()
