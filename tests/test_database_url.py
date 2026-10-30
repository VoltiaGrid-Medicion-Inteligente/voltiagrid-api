"""Database URL built from Secrets Manager parts (US-25, T-25.2). No database needed."""

import pytest
from sqlalchemy import make_url

from app.core.database_url import database_url_from_env, require_database_url

PARTS = {"DB_HOST": "voltiagrid-dev-db.abc.us-east-1.rds.amazonaws.com", "DB_USER": "voltia", "DB_PASSWORD": "s3cr#t"}


def test_database_url_wins_when_set():
    env = {"DATABASE_URL": "postgresql+psycopg://u:p@localhost:5433/voltiagrid", **PARTS}
    assert database_url_from_env(env) == "postgresql+psycopg://u:p@localhost:5433/voltiagrid"


def test_parts_build_an_ssl_url_with_defaults():
    url = make_url(database_url_from_env(PARTS))
    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port, url.database, url.username) == (PARTS["DB_HOST"], 5432, "voltiagrid", "voltia")
    assert url.query["sslmode"] == "require"


@pytest.mark.parametrize("password", ["p@ss:word/with?odd#chars%", "Ab1~!$&'()*+,;=[]"])
def test_password_with_special_characters_survives(password):
    url = make_url(database_url_from_env({**PARTS, "DB_PASSWORD": password}))
    assert url.password == password


def test_port_name_and_sslmode_can_be_changed():
    env = {**PARTS, "DB_PORT": "15432", "DB_NAME": "other", "DB_SSLMODE": "verify-full"}
    url = make_url(database_url_from_env(env))
    assert (url.port, url.database, url.query["sslmode"]) == (15432, "other", "verify-full")


def test_incomplete_parts_name_what_is_missing():
    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        database_url_from_env({"DB_HOST": "h", "DB_USER": "u"})


def test_nothing_configured_returns_none_and_require_fails():
    assert database_url_from_env({}) is None
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        require_database_url({})
