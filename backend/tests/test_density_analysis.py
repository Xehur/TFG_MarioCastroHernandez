"""
Tests del generador de mapas de densidad y de los endpoints de density-map.
"""
import os
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.image import Image
from app.services.analysis import density_generation, density_service


# --- Utilidades --------------------------------------------------------------

def _synthetic_slide_rgb(size=120, block=40):
    """Fondo blanco con un bloque central coloreado (tejido simulado)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    start = (size - block) // 2
    img[start:start + block, start:start + block] = [150, 40, 80]
    return img


class _FakeSlide:
    """Sustituto de OpenSlideService que devuelve una miniatura sintética."""

    def __init__(self, file_path):
        self.file_path = file_path

    def get_thumbnail_rgb(self, max_size=2048):
        return _synthetic_slide_rgb(), 1.0

    def close(self):
        pass


def _make_image_with_file(filename="density_test.svs", user_id=1):
    """Crea un registro Image y un archivo dummy en disco."""
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
    """Evita depender de un archivo WSI real en los tests de endpoint."""
    monkeypatch.setattr(density_service, "OpenSlideService", _FakeSlide)
    yield


# --- Tests del algoritmo -----------------------------------------------------

def test_generate_density_grid_shape():
    mask = np.zeros((120, 120), dtype=bool)
    mask[40:80, 40:80] = True
    result = density_generation.generate_density_map(
        mask, grid_size=30, base_width=120, base_height=120
    )
    assert result.rows == 4 and result.cols == 4
    assert result.density.shape == (4, 4)
    # El bloque central debe tener mayor densidad que las esquinas.
    assert result.density_max > 0
    assert result.density[0, 0] < result.density.max()


def test_generate_density_values_in_range():
    mask = np.ones((60, 60), dtype=bool)
    result = density_generation.generate_density_map(
        mask, grid_size=30, base_width=60, base_height=60
    )
    # Máscara toda tejido -> densidad 1.0 en todas las celdas.
    assert np.allclose(result.density, 1.0)
    assert result.density_mean == pytest.approx(1.0)


def test_generate_density_empty_mask():
    mask = np.zeros((60, 60), dtype=bool)
    result = density_generation.generate_density_map(
        mask, grid_size=30, base_width=60, base_height=60
    )
    assert result.density_max == 0.0
    assert result.density_min == 0.0


def test_generate_density_rejects_small_grid():
    mask = np.ones((20, 20), dtype=bool)
    with pytest.raises(ValueError):
        density_generation.generate_density_map(
            mask, grid_size=4, base_width=20, base_height=20
        )


def test_generate_density_rejects_bad_colormap():
    mask = np.ones((20, 20), dtype=bool)
    with pytest.raises(ValueError):
        density_generation.generate_density_map(
            mask, grid_size=10, base_width=20, base_height=20, colormap="nope"
        )


def test_density_stats_serializable():
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:30, 10:30] = True
    result = density_generation.generate_density_map(
        mask, grid_size=20, base_width=60, base_height=60, colormap="hot"
    )
    stats = result.stats()
    assert stats["colormap"] == "hot"
    assert stats["grid_size"] == 20
    assert isinstance(stats["matrix"], list)
    assert len(stats["matrix"]) == result.rows


def test_density_to_heatmap_rgba():
    density = np.array([[0.0, 0.5], [1.0, 0.25]])
    heat = density_generation.density_to_heatmap_rgba(
        density, out_shape=(20, 20), colormap="viridis"
    )
    assert heat.shape == (20, 20, 4)
    assert heat.dtype == np.uint8
    # Zona de densidad 0 (esquina superior izquierda) es transparente.
    assert heat[0, 0, 3] == 0
    # Zona con densidad > 0 es opaca.
    assert heat[19, 0, 3] > 0


def test_colormap_lut():
    lut = density_generation._colormap_lut("viridis", samples=16)
    assert len(lut) == 16
    assert all(len(c) == 3 for c in lut)


# --- Tests de endpoints ------------------------------------------------------

def test_get_density_map_returns_png(client):
    image_id, _ = _make_image_with_file()
    resp = client.get(f"/images/{image_id}/density-map", params={"grid_size": 30})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_density_map_stats(client):
    image_id, _ = _make_image_with_file(filename="density_test2.svs")
    resp = client.get(
        f"/images/{image_id}/density-map/stats", params={"grid_size": 30}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["grid_size"] == 30
    assert "matrix" in data["density_data"]
    assert data["density_data"]["colormap"] == "viridis"
    assert data["image_id"] == image_id


def test_density_map_is_cached(client):
    image_id, _ = _make_image_with_file(filename="density_test3.svs")
    first = client.get(
        f"/images/{image_id}/density-map/stats", params={"grid_size": 30}
    ).json()
    second = client.get(
        f"/images/{image_id}/density-map/stats", params={"grid_size": 30}
    ).json()
    assert first["id"] == second["id"]


def test_density_map_different_grid_creates_new(client):
    image_id, _ = _make_image_with_file(filename="density_test4.svs")
    a = client.get(
        f"/images/{image_id}/density-map/stats", params={"grid_size": 30}
    ).json()
    b = client.get(
        f"/images/{image_id}/density-map/stats", params={"grid_size": 60}
    ).json()
    assert a["id"] != b["id"]
    assert b["grid_size"] == 60


def test_analyze_density_forces_regeneration(client):
    image_id, _ = _make_image_with_file(filename="density_test5.svs")
    first = client.get(
        f"/images/{image_id}/density-map/stats", params={"grid_size": 30}
    ).json()
    resp = client.post(
        f"/images/{image_id}/analyze/density", params={"grid_size": 30}
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == first["id"]


def test_density_map_invalid_grid_size(client):
    image_id, _ = _make_image_with_file(filename="density_test6.svs")
    resp = client.get(
        f"/images/{image_id}/density-map", params={"grid_size": 2}
    )
    assert resp.status_code == 422


def test_density_map_invalid_colormap(client):
    image_id, _ = _make_image_with_file(filename="density_test7.svs")
    resp = client.get(
        f"/images/{image_id}/density-map",
        params={"grid_size": 30, "colormap": "nope"},
    )
    assert resp.status_code == 422


def test_density_map_image_not_found(client):
    resp = client.get("/images/99999/density-map", params={"grid_size": 30})
    assert resp.status_code == 404


def test_density_map_requires_auth(anon_client):
    image_id, _ = _make_image_with_file(filename="density_test8.svs")
    resp = anon_client.get(
        f"/images/{image_id}/density-map", params={"grid_size": 30}
    )
    assert resp.status_code in (401, 403)
