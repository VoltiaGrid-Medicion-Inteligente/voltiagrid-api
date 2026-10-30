"""APIs behind the load balancer with a path prefix (US-27, T-27.3). No database needed.

The ALB forwards /control-center/... to the control center without removing the prefix. With
ROOT_PATH=/control-center, FastAPI routes /control-center/health to /health, and /health keeps working
for the container health check.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.control_center.main import app as control_center
from app.api.customer_consumption.main import app as customer_consumption
from app.api.network_inventory.main import app as network_inventory
from app.core.config import get_settings
from simulators.transformer_api.main import app as transformer_metering

APPS = [
    (customer_consumption, "/consumption"),
    (control_center, "/control-center"),
    (network_inventory, "/inventory"),
    (transformer_metering, "/f5"),
]


def test_root_path_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("ROOT_PATH", "/control-center")
    get_settings.cache_clear()
    try:
        assert get_settings().root_path == "/control-center"
    finally:
        get_settings.cache_clear()


def test_no_prefix_by_default(monkeypatch):
    monkeypatch.delenv("ROOT_PATH", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().root_path == ""
    finally:
        get_settings.cache_clear()


@pytest.fixture
def with_prefix():
    changed = []

    def apply(app, prefix):
        changed.append((app, app.root_path))
        app.root_path = prefix
        return TestClient(app)

    yield apply
    for app, original in changed:
        app.root_path = original


@pytest.mark.parametrize("app,prefix", APPS)
def test_health_answers_with_and_without_the_prefix(with_prefix, app, prefix):
    client = with_prefix(app, prefix)
    assert client.get(f"{prefix}/health").status_code == 200
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("app,prefix", APPS)
def test_docs_point_to_the_prefixed_contract(with_prefix, app, prefix):
    client = with_prefix(app, prefix)
    docs = client.get(f"{prefix}/docs")
    assert docs.status_code == 200
    assert f"{prefix}/openapi.json" in docs.text
    assert client.get(f"{prefix}/openapi.json").status_code == 200
