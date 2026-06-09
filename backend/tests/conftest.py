"""
Configuración global para tests
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, SessionLocal
from app import db


@pytest.fixture(scope="function")
def db_setup():
    """
    Crea una BD SQLite en memoria para tests
    """
    SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            database = TestingSessionLocal()
            yield database
        finally:
            database.close()

    app.dependency_overrides[db.SessionLocal] = override_get_db

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_setup):
    """
    Fixture que proporciona un cliente de test para la API
    """
    return TestClient(app)