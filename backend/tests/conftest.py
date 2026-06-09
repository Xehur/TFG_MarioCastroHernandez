"""
Configuración global para tests
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """
    Fixture que proporciona un cliente de test para la API
    """
    return TestClient(app)