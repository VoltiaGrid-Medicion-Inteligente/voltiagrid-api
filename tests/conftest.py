"""pytest fixtures for database testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

# Load .env for DATABASE_URL
load_dotenv()

# Test-only values so the API tests can issue and validate tokens (T-13.1).
# They replace whatever .env says: tests never use the real secret.
os.environ["JWT_SECRET"] = "test-only-secret-not-used-anywhere-else-0123456789"
os.environ["DEMO_CUSTOMER_PASSWORD"] = "test-customer-password"
os.environ["DEMO_INTERNAL_PASSWORD"] = "test-internal-password"


@pytest.fixture(scope="session")
def engine():
    """Engine compartido para toda la sesión de tests."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL no configurada")
    return create_engine(database_url)


@pytest.fixture
def session(engine):
    """Sesión con transacción que hace rollback al final."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()  # Limpia todo lo que hizo el test
    connection.close()

@pytest.fixture
def consumption_app():
    """Customer consumption API without a database: every CU-MACxxxxxx exists and owns meter MACxxxxxx."""
    from app.api.customer_consumption.main import app
    from app.api.customer_consumption.repository import get_repository

    class AnyMacCustomer:
        def customer_exists(self, customer_code: str) -> bool:
            return customer_code.startswith("CU-MAC")

        def meter_ids(self, customer_code: str) -> list[str]:
            return [customer_code.removeprefix("CU-")]

    app.dependency_overrides[get_repository] = AnyMacCustomer
    yield app
    app.dependency_overrides.pop(get_repository, None)


F5_TEST_INVENTORY = {
    "TR-00001": [f"MAC{i:06d}" for i in range(1, 61)],
    "TR-00002": [f"MAC{i:06d}" for i in range(61, 131)],
}


@pytest.fixture
def f5_test_client():
    """A real F5 app (simulators/transformer_api) on a synthetic inventory, used as the control center's F5."""
    from fastapi.testclient import TestClient

    from app.api.control_center.f5_client import F5Client
    from simulators.common.inventory import Inventory
    from simulators.transformer_api.losses import LossStore
    from simulators.transformer_api.main import app as f5_app
    from simulators.transformer_api.main import get_inventory, get_loss_store, get_seed

    store = LossStore()
    f5_app.dependency_overrides[get_inventory] = lambda: Inventory(F5_TEST_INVENTORY)
    f5_app.dependency_overrides[get_loss_store] = lambda: store
    f5_app.dependency_overrides[get_seed] = lambda: 42
    http = TestClient(f5_app)
    yield F5Client(http)
    f5_app.dependency_overrides.clear()


@pytest.fixture
def control_center_app(f5_test_client):
    """Control center without a database: F4 has TR-00001 (141 kVA) and TR-00002 (2 kVA, always overloaded)."""
    from decimal import Decimal

    from app.api.control_center.f5_client import get_f5_client
    from app.api.control_center.main import app
    from app.api.control_center.repository import TransformerInfo, get_repository

    transformers = [TransformerInfo("TR-00001", "CT-000", Decimal("141.00")),
                    TransformerInfo("TR-00002", "CT-000", Decimal("2.00"))]

    class FakeRepository:
        def get_transformer(self, code):
            return next((t for t in transformers if t.code == code), None)

        def list_transformers(self, circuit_code=None):
            return [t for t in transformers if circuit_code in (None, t.circuit_code)]

    app.dependency_overrides[get_repository] = FakeRepository
    app.dependency_overrides[get_f5_client] = lambda: f5_test_client
    yield app
    app.dependency_overrides.pop(get_repository, None)
    app.dependency_overrides.pop(get_f5_client, None)
