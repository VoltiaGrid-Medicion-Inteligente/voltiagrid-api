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

        def stored_daily(self, customer_code, first, last) -> list[dict]:
            return []

        def events(self, customer_code, first, last) -> list[dict]:
            return []

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


@pytest.fixture
def rabbitmq_url():
    """A RabbitMQ only for tests (US-29). Set RABBITMQ_TEST_URL to run these tests; the CI sets it.

    The fixture deletes the reading queues before and after each test, so never point it at a broker with
    data you want to keep (that is why it does not use RABBITMQ_URL from .env).
    """
    url = os.getenv("RABBITMQ_TEST_URL")
    if not url:
        pytest.skip("RABBITMQ_TEST_URL not set")
    import pika
    from pika.exceptions import AMQPConnectionError

    from ingestion.topology import BINDINGS, DEAD_LETTER_QUEUE

    def drop_queues():
        connection = pika.BlockingConnection(pika.URLParameters(url))
        channel = connection.channel()
        for queue in [*BINDINGS, DEAD_LETTER_QUEUE]:
            channel.queue_delete(queue=queue)
        connection.close()

    try:
        drop_queues()
    except AMQPConnectionError:
        pytest.skip("RabbitMQ not reachable at RABBITMQ_TEST_URL")
    yield url
    drop_queues()
