"""
Tests del análisis de zonas anotadas (anotaciones como WSI aparte).

Cubren la geometría (bbox + máscara de forma), los servicios y los endpoints
``/annotations/{id}/...`` reutilizando una miniatura sintética para no depender
de un archivo WSI real.
"""
import os
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.image import Image
from app.services.analysis import annotation_analysis_service


# --- Utilidades --------------------------------------------------------------

def _synthetic_region(size=100, block=40):
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    start = (size - block) // 2
    img[start:start + block, start:start + block] = [150, 40, 80]
    return img


class _FakeSlide:
    """Sustituto de OpenSlideService que devuelve una región sintética."""

    def __init__(self, file_path):
        self.file_path = file_path

    def read_region_rgb(self, x, y, width, height, max_size=2048):
        return _synthetic_region(), 1.0, (int(x), int(y), 100, 100)

    def close(self):
        pass


def _make_image_with_file(filename="ann_analysis.svs", user_id=1):
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
            width=1000,
            height=800,
            level_count=1,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image.id, file_path
    finally:
        db.close()


def _create_annotation(client, image_id, payload):
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


_RECT = {
    "shape_type": "rectangle",
    "coordinates": {"x": 100, "y": 100, "width": 200, "height": 150},
    "color": "#FF0000",
}
_CIRCLE = {
    "shape_type": "circle",
    "coordinates": {"x": 200, "y": 200, "radius": 80},
    "color": "#00FF00",
}


@pytest.fixture(autouse=True)
def _patch_slide(monkeypatch):
    monkeypatch.setattr(
        annotation_analysis_service, "OpenSlideService", _FakeSlide
    )
    yield


# --- Geometría ---------------------------------------------------------------

def test_bbox_rectangle():
    x, y, w, h = annotation_analysis_service.annotation_bbox(
        "rectangle", {"x": 10, "y": 20, "width": 30, "height": 40}
    )
    assert (x, y, w, h) == (10, 20, 30, 40)


def test_bbox_circle():
    x, y, w, h = annotation_analysis_service.annotation_bbox(
        "circle", {"x": 50, "y": 60, "radius": 10}
    )
    assert (x, y, w, h) == (40, 50, 20, 20)


def test_bbox_polygon():
    x, y, w, h = annotation_analysis_service.annotation_bbox(
        "polygon", {"points": [[10, 10], [30, 20], [20, 40]]}
    )
    assert (x, y, w, h) == (10, 10, 20, 30)


def test_shape_mask_rectangle_is_none():
    mask = annotation_analysis_service._shape_mask(
        "rectangle", {}, (0, 0, 100, 100), 100, 100, 1.0
    )
    assert mask is None


def test_shape_mask_circle_excludes_corners():
    mask = annotation_analysis_service._shape_mask(
        "circle",
        {"x": 50, "y": 50, "radius": 50},
        (0, 0, 100, 100),
        100,
        100,
        1.0,
    )
    assert mask is not None
    assert mask[50, 50]  # centro dentro
    assert not mask[0, 0]  # esquina fuera


# --- Endpoints: tejido -------------------------------------------------------

def test_annotation_tissue_mask_png(client):
    image_id, _ = _make_image_with_file()
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/tissue-mask")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_annotation_tissue_stats(client):
    image_id, _ = _make_image_with_file(filename="ann_analysis2.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/tissue-mask/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["annotation_id"] == ann_id
    assert data["analysis_type"] == "tissue_mask"
    assert "tissue_percent" in data["result_data"]


def test_annotation_tissue_cached(client):
    image_id, _ = _make_image_with_file(filename="ann_analysis3.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    first = client.get(f"/annotations/{ann_id}/tissue-mask/stats").json()
    second = client.get(f"/annotations/{ann_id}/tissue-mask/stats").json()
    assert first["id"] == second["id"]


# --- Endpoints: densidad -----------------------------------------------------

def test_annotation_density_png(client):
    image_id, _ = _make_image_with_file(filename="ann_analysis4.svs")
    ann_id = _create_annotation(client, image_id, _CIRCLE)
    resp = client.get(f"/annotations/{ann_id}/density-map")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_annotation_density_stats(client):
    image_id, _ = _make_image_with_file(filename="ann_analysis5.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/density-map/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["annotation_id"] == ann_id
    assert "matrix" in data["density_data"]


# --- Endpoints: consolidado + analíticas -------------------------------------

def test_annotation_full_analysis_and_analytics(client):
    image_id, _ = _make_image_with_file(filename="ann_analysis6.svs")
    ann_id = _create_annotation(client, image_id, _RECT)

    resp = client.post(f"/annotations/{ann_id}/analyze")
    assert resp.status_code == 201
    summary = resp.json()
    assert summary["annotation_id"] == ann_id
    assert "tissue" in summary["result_data"]
    assert "density" in summary["result_data"]

    analysis = client.get(f"/annotations/{ann_id}/analysis")
    assert analysis.status_code == 200

    analytics = client.get(f"/annotations/{ann_id}/analytics")
    assert analytics.status_code == 200
    adata = analytics.json()
    assert adata["annotation_id"] == ann_id
    assert adata["total_annotations"] == 0
    assert adata["tissue"] is not None
    assert adata["density_zones"] is not None


def test_annotation_not_found(client):
    resp = client.get("/annotations/99999/tissue-mask")
    assert resp.status_code == 404


def test_annotation_analysis_requires_auth(anon_client):
    image_id, _ = _make_image_with_file(filename="ann_analysis7.svs")
    resp = anon_client.get(f"/annotations/1/tissue-mask")
    assert resp.status_code in (401, 403)


def test_image_analytics_ignores_annotation_rows(client):
    """Las analíticas de imagen no deben mezclar resultados de anotaciones."""
    image_id, _ = _make_image_with_file(filename="ann_analysis8.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    client.post(f"/annotations/{ann_id}/analyze")

    # La imagen no tiene análisis propio: tejido y densidad deben ser None.
    resp = client.get(f"/images/{image_id}/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tissue"] is None
    assert data["density_zones"] is None
