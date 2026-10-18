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