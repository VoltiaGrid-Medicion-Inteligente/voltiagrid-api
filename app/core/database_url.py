"""Database URL from the environment (US-25, T-25.2).

Locally (docker-compose, tests) the whole URL comes in DATABASE_URL.
In AWS, ECS reads the user and the password from Secrets Manager and injects them as DB_USER and
DB_PASSWORD; host, port and database name come as plain variables. The URL is built here so the
password is escaped correctly and SSL is required (RDS has rds.force_ssl = 1).

Used by the APIs, the seed, the migrations and the F5 simulator.
"""

import os
from collections.abc import Mapping

from sqlalchemy import URL

REQUIRED_PARTS = ("DB_HOST", "DB_USER", "DB_PASSWORD")


def database_url_from_env(environ: Mapping[str, str] | None = None) -> str | None:
    """DATABASE_URL if set, otherwise the URL built from DB_* parts, otherwise None."""
    env = os.environ if environ is None else environ
    if env.get("DATABASE_URL"):
        return env["DATABASE_URL"]
    if not any(env.get(name) for name in REQUIRED_PARTS):
        return None
    missing = [name for name in REQUIRED_PARTS if not env.get(name)]
    if missing:
        raise RuntimeError(f"Database settings incomplete, missing: {', '.join(missing)}")
    url = URL.create(
        "postgresql+psycopg",
        username=env["DB_USER"],
        password=env["DB_PASSWORD"],
        host=env["DB_HOST"],
        port=int(env.get("DB_PORT") or 5432),
        database=env.get("DB_NAME") or "voltiagrid",
        query={"sslmode": env.get("DB_SSLMODE") or "require"},
    )
    return url.render_as_string(hide_password=False)


def require_database_url(environ: Mapping[str, str] | None = None) -> str:
    url = database_url_from_env(environ)
    if not url:
        raise RuntimeError("Set DATABASE_URL, or DB_HOST, DB_USER and DB_PASSWORD (see .env.example)")
    return url
