"""
Tests de la clasificación de tejido por IA (Sprint 7).

Cubren las funciones puras (rejilla, leyenda, resumen), ``classify_rgb`` con un
modelo simulado (para no descargar/ejecutar el modelo real) y los endpoints
``/images|annotations/{id}/ai-classification``.
"""
import os

import numpy as np
import pytest
import torch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.image import Image
from app.services.analysis import ai_classification_service as ai
from app.services.analysis import annotation_analysis_service


# --- Utilidades --------------------------------------------------------------

def _tissue_region(h=120, w=160, margin=16):
    """Región RGB con borde claro e interior de 'tejido' (saturado y oscuro).

    La variación claro/oscuro es necesaria para que la detección de tejido por
    Otsu pueda segmentar (una imagen uniforme no tiene umbral).
    """
    img = np.full((h, w, 3), (235, 235, 235), dtype=np.uint8)
    img[margin:h - margin, margin:w - margin] = (150, 40, 80)
    return img


class _FakeSlide:
    """Sustituto de OpenSlideService que devuelve una región de tejido."""

    def __init__(self, file_path):
        self.file_path = file_path

    def get_thumbnail_rgb(self, max_size=2048):
        return _tissue_region(), 1.0

    def read_region_rgb(self, x, y, width, height, max_size=2048):
        return _tissue_region(), 1.0, (int(x), int(y), 160, 120)

    def get_mpp_x(self):
        return 0.5

    def read_patch_rgb(self, center_x, center_y, size_level0, out_size=224):
        # Parche de "tejido" (saturado/oscuro) a la resolución del modelo.
        return np.full((out_size, out_size, 3), (150, 40, 80), dtype=np.uint8)

    def close(self):
        pass


class _FakeModel:
    """Modelo simulado: predice siempre la clase 'TUM' (índice 3)."""

    def eval(self):
        return self

    def __call__(self, tensor):
        n = tensor.shape[0]
        out = torch.zeros(n, 9)
        out[:, 3] = 10.0
        return out


@pytest.fixture(autouse=True)
def _patch_ai(monkeypatch):
    monkeypatch.setattr(ai, "OpenSlideService", _FakeSlide)
    monkeypatch.setattr(annotation_analysis_service, "OpenSlideService", _FakeSlide)
    monkeypatch.setattr(ai, "get_model", lambda: _FakeModel())
    yield


def _make_image_with_file(filename="ai_test.svs", user_id=1):
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


# --- Funciones puras ---------------------------------------------------------

def test_grid_shape_proporcional():
    cols, rows = ai._grid_shape(1000, 500, 200)
    assert cols >= rows
    assert cols * rows <= 260


def test_class_legend():
    legend = ai.class_legend()
    assert len(legend) == 9
    codes = {c["code"] for c in legend}
    assert {"TUM", "STR", "DEB", "BACK"}.issubset(codes)


def test_build_summary_percentages():
    counts = {c: 0 for c in ai.CLASS_CODES}
    counts["TUM"] = 6
    counts["STR"] = 2
    counts["BACK"] = 100  # el fondo se excluye del reparto
    summary = ai._build_summary(counts)
    assert summary["dominant_class"] == "TUM"
    assert summary["dominant_group"] == "Tumoral"
    total = sum(g["percent"] for g in summary["groups"])
    assert abs(total - 100.0) < 0.1
    tum = next(c for c in summary["classes"] if c["code"] == "TUM")
    assert tum["percent"] == 75.0


def test_build_summary_sin_tejido():
    counts = {c: 0 for c in ai.CLASS_CODES}
    counts["BACK"] = 10
    summary = ai._build_summary(counts)
    assert summary["dominant_class"] is None
    assert summary["dominant_group"] is None


def test_classify_rgb_con_modelo_simulado(monkeypatch):
    monkeypatch.setattr(ai, "get_model", lambda: _FakeModel())
    rgb = _tissue_region()
    mask = np.ones(rgb.shape[:2], dtype=bool)
    result = ai.classify_rgb(rgb, mask, max_patches=64)
    assert result["overlay"].shape == (rgb.shape[0], rgb.shape[1], 4)
    assert result["tissue_patches"] > 0
    # Todas las celdas de tejido se clasifican como TUM (índice 3).
    assert result["counts"]["TUM"] == result["tissue_patches"]
    # El overlay usa el color del GRUPO (Tumoral -> rojo), no el de la clase.
    painted = result["overlay"][..., 3] > 0
    assert painted.any()
    r, g, b = ai.GROUP_COLORS["Tumoral"]
    assert (result["overlay"][painted, 0] == r).all()
    assert (result["overlay"][painted, 1] == g).all()
    assert (result["overlay"][painted, 2] == b).all()


class _FakeModelLym:
    """Modelo simulado que predice siempre 'LYM' (índice 8, grupo No tumoral)."""

    def eval(self):
        return self

    def __call__(self, tensor):
        out = torch.zeros(tensor.shape[0], 9)
        out[:, 8] = 10.0
        return out


def test_overlay_usa_color_de_grupo_no_tumoral(monkeypatch):
    monkeypatch.setattr(ai, "get_model", lambda: _FakeModelLym())
    rgb = _tissue_region()
    mask = np.ones(rgb.shape[:2], dtype=bool)
    result = ai.classify_rgb(rgb, mask, max_patches=64)
    painted = result["overlay"][..., 3] > 0
    assert painted.any()
    # Linfocitos pertenece a "No tumoral" -> debe pintarse verde (color de grupo),
    # NO con el color de clase morado.
    green = ai.GROUP_COLORS["No tumoral"]
    assert (result["overlay"][painted, 0] == green[0]).all()
    assert (result["overlay"][painted, 1] == green[1]).all()
    assert (result["overlay"][painted, 2] == green[2]).all()


# --- Endpoints: imagen -------------------------------------------------------

def test_image_ai_stats(client):
    image_id, _ = _make_image_with_file("ai_img1.svs")
    resp = client.get(f"/images/{image_id}/ai-classification/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_type"] == "ai_classification"
    rd = data["result_data"]
    assert rd["dominant_class"] == "TUM"
    assert rd["dominant_group"] == "Tumoral"
    assert len(rd["classes"]) == 8  # 9 clases menos el fondo
    assert rd["model"]["dataset"] == "NCT-CRC-HE-100K"


def test_image_ai_png(client):
    image_id, _ = _make_image_with_file("ai_img2.svs")
    resp = client.get(f"/images/{image_id}/ai-classification")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_ai_analyze_post(client):
    image_id, _ = _make_image_with_file("ai_img3.svs")
    resp = client.post(f"/images/{image_id}/analyze/ai")
    assert resp.status_code == 201
    assert resp.json()["result_data"]["dominant_class"] == "TUM"


def test_image_ai_cached(client):
    image_id, _ = _make_image_with_file("ai_img4.svs")
    first = client.get(f"/images/{image_id}/ai-classification/stats").json()
    second = client.get(f"/images/{image_id}/ai-classification/stats").json()
    assert first["id"] == second["id"]


def test_image_ai_requires_auth(anon_client):
    image_id, _ = _make_image_with_file("ai_img5.svs")
    resp = anon_client.get(f"/images/{image_id}/ai-classification/stats")
    assert resp.status_code in (401, 403)


# --- Endpoints: anotación ----------------------------------------------------

def test_annotation_ai_stats(client):
    image_id, _ = _make_image_with_file("ai_ann1.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/ai-classification/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["annotation_id"] == ann_id
    assert data["analysis_type"] == "ai_classification"
    assert data["result_data"]["dominant_class"] == "TUM"


def test_annotation_ai_png(client):
    image_id, _ = _make_image_with_file("ai_ann2.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/ai-classification")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
