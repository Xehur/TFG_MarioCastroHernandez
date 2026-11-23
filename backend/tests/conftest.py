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
    from app.core import deps
    app.dependency_overrides[users.get_db] = override_get_db
    app.dependency_overrides[images.get_db] = override_get_db
    app.dependency_overrides[deps.get_db] = override_get_db

    yield

    # Limpiar al final
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db_setup) -> TestClient:
    """Cliente de test SIN autenticar (para probar protección de endpoints)."""
    return TestClient(app)


@pytest.fixture
def auth_headers(anon_client) -> dict:
    """
    Registra un usuario de prueba y devuelve la cabecera Authorization
    con un token JWT válido.
    """
    resp = anon_client.post(
        "/auth/register",
        json={
            "email": "testauth@example.com",
            "password": "testpass123",
            "full_name": "Test Auth User",
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(db_setup, auth_headers) -> TestClient:
    """
    Fixture que proporciona un cliente de test YA autenticado.
    Incluye por defecto la cabecera Bearer en todas las peticiones.
    """
    test_client = TestClient(app)
    test_client.headers.update(auth_headers)
    return test_client


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
    Fixture que limpia archivos de prueba del directorio uploads después de cada test.

    Los tests crean ficheros .svs falsos de unos pocos bytes con nombres muy
    variados (ai_img*, density_test*, rt_test*, tissue_*, ann_analysis*,
    cmd_exec*, test*, ...). Para no dejar basura en uploads, se eliminan todos
    los .svs pequeños (los WSI reales pesan MB), preservando las imágenes reales.
    """
    yield

    if not os.path.exists(settings.UPLOAD_DIR):
        return

    _FAKE_SVS_MAX_BYTES = 1024  # los WSI reales pesan MB; los fakes de test, bytes

    for filename in os.listdir(settings.UPLOAD_DIR):
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            is_prefixed = filename.startswith("test") or filename.startswith("large_test")
            is_small_fake_svs = (
                filename.lower().endswith(".svs")
                and os.path.getsize(filepath) < _FAKE_SVS_MAX_BYTES
            )
            if is_prefixed or is_small_fake_svs:
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