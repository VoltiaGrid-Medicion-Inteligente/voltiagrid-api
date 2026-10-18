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