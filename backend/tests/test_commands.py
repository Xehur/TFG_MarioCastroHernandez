"""
Tests de la paleta de comandos: registro, listado/filtro y ejecución (issue 36).
"""
import os
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.image import Image
from app.services.analysis import tissue_service, density_service
from app.services.commands import command_registry, command_executor


def _synthetic_slide_rgb(size=120, block=40):
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    start = (size - block) // 2
    img[start:start + block, start:start + block] = [150, 40, 80]
    return img


class _FakeSlide:
    def __init__(self, file_path):
        self.file_path = file_path

    def get_thumbnail_rgb(self, max_size=2048):
        return _synthetic_slide_rgb(), 1.0

    def close(self):
        pass


def _make_image_with_file(filename="cmd_test.svs", user_id=1):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(file_path, "wb") as fh:
        fh.write(b"dummy")

    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        image = Image(
            filename=filename,
            file_path=file_path,
            user_id=user_id,
            width=120,
            height=120,
            level_count=1,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image.id, file_path
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _patch_slide(monkeypatch):
    monkeypatch.setattr(tissue_service, "OpenSlideService", _FakeSlide)
    monkeypatch.setattr(density_service, "OpenSlideService", _FakeSlide)
    yield


# --- Registro ----------------------------------------------------------------

def test_registry_lists_all_commands():
    commands = command_registry.list_commands()
    assert len(commands) >= 10
    ids = {c["id"] for c in commands}
    assert "run-full-analysis" in ids
    assert "open-analytics-dashboard" in ids


def test_registry_filter_by_query_accent_insensitive():
    # "analisis" sin acento debe encontrar comandos de "Análisis".
    result = command_registry.list_commands(query="analisis")
    assert result
    assert all(
        "analisis" in command_registry._normalize(
            c["name"] + c["description"] + c["category"] + " ".join(c["keywords"])
        )
        for c in result
    )


def test_registry_filter_by_category():
    result = command_registry.list_commands(category=command_registry.CATEGORY_ANNOTATIONS)
    assert result
    assert all(c["category"] == command_registry.CATEGORY_ANNOTATIONS for c in result)


def test_registry_categories_unique():
    cats = command_registry.list_categories()
    assert len(cats) == len(set(cats))
    assert command_registry.CATEGORY_ANALYSIS in cats


# --- Endpoint GET /commands --------------------------------------------------

def test_get_commands_returns_list(client):
    resp = client.get("/commands")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == len(data["commands"])
    assert data["total"] > 0
    assert "categories" in data


def test_get_commands_search_filter(client):
    resp = client.get("/commands", params={"q": "densidad"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("densi" in c["name"].lower() or "densi" in c["description"].lower()
               for c in data["commands"])


def test_get_commands_category_filter(client):
    resp = client.get(
        "/commands", params={"category": command_registry.CATEGORY_NAVIGATION}
    )
    assert resp.status_code == 200
    for c in resp.json()["commands"]:
        assert c["category"] == command_registry.CATEGORY_NAVIGATION


def test_get_commands_requires_auth(anon_client):
    resp = anon_client.get("/commands")
    assert resp.status_code in (401, 403)


def test_get_categories(client):
    resp = client.get("/commands/categories")
    assert resp.status_code == 200
    assert command_registry.CATEGORY_ANALYSIS in resp.json()["categories"]


# --- Endpoint POST /commands/execute -----------------------------------------

def test_execute_run_full_analysis(client):
    image_id, _ = _make_image_with_file(filename="cmd_exec1.svs")
    resp = client.post(
        "/commands/execute",
        json={"command_id": "run-full-analysis", "params": {"image_id": image_id}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "analysis_id" in data["result"]
    assert "summary" in data["result"]


def test_execute_detect_tissue(client):
    image_id, _ = _make_image_with_file(filename="cmd_exec2.svs")
    resp = client.post(
        "/commands/execute",
        json={"command_id": "detect-tissue", "params": {"image_id": image_id}},
    )
    assert resp.status_code == 200
    assert "stats" in resp.json()["result"]


def test_execute_generate_density_map(client):
    image_id, _ = _make_image_with_file(filename="cmd_exec3.svs")
    resp = client.post(
        "/commands/execute",
        json={"command_id": "generate-density-map", "params": {"image_id": image_id}},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "density_map_id" in result


def test_execute_unknown_command_404(client):
    resp = client.post(
        "/commands/execute", json={"command_id": "does-not-exist", "params": {}}
    )
    assert resp.status_code == 404


def test_execute_frontend_command_rejected(client):
    resp = client.post(
        "/commands/execute",
        json={"command_id": "open-analytics-dashboard", "params": {}},
    )
    assert resp.status_code == 400


def test_execute_missing_image_id_422(client):
    resp = client.post(
        "/commands/execute", json={"command_id": "run-full-analysis", "params": {}}
    )
    assert resp.status_code == 422


def test_execute_image_not_found_404(client):
    resp = client.post(
        "/commands/execute",
        json={"command_id": "detect-tissue", "params": {"image_id": 99999}},
    )
    assert resp.status_code == 404


def test_execute_requires_auth(anon_client):
    resp = anon_client.post(
        "/commands/execute",
        json={"command_id": "run-full-analysis", "params": {"image_id": 1}},
    )
    assert resp.status_code in (401, 403)


# --- Ejecutor (unidad) -------------------------------------------------------

def test_executor_invalid_image_id_type():
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(command_executor.CommandError) as exc:
            command_executor.execute(
                db, "detect-tissue", {"image_id": "abc"}
            )
        assert exc.value.status_code == 422
    finally:
        db.close()
