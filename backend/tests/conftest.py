"""
Configuración global para tests
"""
import pytest
import os
import io
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import UploadFile

from app.main import app
from app.db import Base, SessionLocal
from app import db
from app.config import settings


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

    # Limpiar tablas existentes antes de crear nuevas
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            database = TestingSessionLocal()
            yield database
        finally:
            database.close()

    # Override para que los tests usen la BD de test
    from app.routers import users, images
    app.dependency_overrides[users.get_db] = override_get_db
    app.dependency_overrides[images.get_db] = override_get_db

    yield

    # Limpiar al final
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_setup) -> TestClient:
    """
    Fixture que proporciona un cliente de test para la API
    """
    return TestClient(app)


@pytest.fixture
def test_db(db_setup) -> Generator[Session, None, None]:
    """
    Fixture que proporciona una sesión de BD de test
    """
    SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_svs_file() -> UploadFile:
    """
    Fixture que crea un archivo .svs simulado para tests
    """
    return UploadFile(
        filename="test.svs",
        file=io.BytesIO(b"fake svs content")
    )


@pytest.fixture
def mock_tiff_file() -> UploadFile:
    """
    Fixture que crea un archivo .tiff simulado para tests
    """
    return UploadFile(
        filename="test.tiff",
        file=io.BytesIO(b"fake tiff content")
    )


@pytest.fixture
def mock_invalid_file() -> UploadFile:
    """
    Fixture que crea un archivo con extensión inválida para tests
    """
    return UploadFile(
        filename="test.jpg",
        file=io.BytesIO(b"fake jpg content")
    )


@pytest.fixture
def mock_large_file() -> UploadFile:
    """
    Fixture que crea un archivo grande simulado (10MB) para tests
    """
    file_size = 10 * 1024 * 1024  # 10MB
    return UploadFile(
        filename="large_test.svs",
        file=io.BytesIO(b"x" * file_size)
    )


@pytest.fixture(autouse=True)
def cleanup_uploads():
    """
    Fixture que limpia archivos de prueba del directorio uploads después de cada test
    """
    yield
    
    # Limpiar archivos de test después de ejecutar
    if os.path.exists(settings.UPLOAD_DIR):
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith("test") or filename.startswith("large_test"):
                filepath = os.path.join(settings.UPLOAD_DIR, filename)
                try:
                    os.remove(filepath)
                except Exception:
                    pass  # Ignorar errores de limpieza


@pytest.fixture
def sample_image_metadata() -> dict:
    """
    Fixture que proporciona metadatos de imagen de ejemplo
    """
    return {
        "filename": "test.svs",
        "user_id": 1,
        "width": 35868,
        "height": 16704,
        "level_count": 3,
        "downsamples": [1.0, 4.0, 16.0],
        "properties": {
            "aperio.AppMag": "20",
            "aperio.MPP": "0.4991",
            "openslide.vendor": "aperio"
        },
        "file_size_mb": 83.4
    }