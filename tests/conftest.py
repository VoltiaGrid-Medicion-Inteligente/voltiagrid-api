"""pytest fixtures for database testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

# Load .env for DATABASE_URL
load_dotenv()


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