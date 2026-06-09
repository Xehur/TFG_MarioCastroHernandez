"""
Tests para endpoints de salud
"""
import pytest


def test_root_endpoint(client):
    """
    Test del endpoint raíz
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["version"] == "0.1.0"


def test_health_endpoint(client):
    """
    Test del endpoint /health/
    """
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "WSI Backend API"


def test_liveness_endpoint(client):
    """
    Test del endpoint /health/live
    """
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_endpoint(client):
    """
    Test del endpoint /health/ready
    """
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_docs_endpoint(client):
    """
    Test que la documentación Swagger está disponible
    """
    response = client.get("/docs")
    assert response.status_code == 200