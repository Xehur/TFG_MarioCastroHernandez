"""
Tests del servicio de análisis consolidado y de sus endpoints (issue 37).
"""
import os
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.image import Image
from app.services.analysis import tissue_service, density_service, analysis_service


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


def _make_image_with_file(filename="rt_test.svs", user_id=1):
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


# --- Tests de endpoints ------------------------------------------------------

def test_analyze_image_returns_full_summary(client):
    image_id, _ = _make_image_with_file()
    resp = client.post(f"/images/{image_id}/analyze", params={"grid_size": 30})
    assert resp.status_code == 201
    data = resp.json()
    assert data["analysis_type"] == "full_analysis"
    assert data["image_id"] == image_id
    result = data["result_data"]
    assert "tissue" in result and "density" in result
    assert "tissue_percent" in result["tissue"]
    assert result["density"]["grid_size"] == 30
    assert "analyzed_at" in result


def test_analyze_image_persists_and_reuses_record(client):
    image_id, _ = _make_image_with_file(filename="rt_test2.svs")
    first = client.post(
        f"/images/{image_id}/analyze", params={"grid_size": 30}
    ).json()
    second = client.post(
        f"/images/{image_id}/analyze", params={"grid_size": 30}
    ).json()
    # El registro consolidado se actualiza in-place (mismo id).
    assert first["id"] == second["id"]


def test_get_analysis_returns_latest(client):
    image_id, _ = _make_image_with_file(filename="rt_test3.svs")
    client.post(f"/images/{image_id}/analyze", params={"grid_size": 30})
    resp = client.get(f"/images/{image_id}/analysis")
    assert resp.status_code == 200
    assert resp.json()["analysis_type"] == "full_analysis"


def test_get_analysis_404_when_missing(client):
    image_id, _ = _make_image_with_file(filename="rt_test4.svs")
    resp = client.get(f"/images/{image_id}/analysis")
    assert resp.status_code == 404


def test_analyze_image_invalid_colormap(client):
    image_id, _ = _make_image_with_file(filename="rt_test5.svs")
    resp = client.post(
        f"/images/{image_id}/analyze",
        params={"grid_size": 30, "colormap": "nope"},
    )
    assert resp.status_code == 422


def test_analyze_image_not_found(client):
    resp = client.post("/images/99999/analyze", params={"grid_size": 30})
    assert resp.status_code == 404


def test_analyze_image_requires_auth(anon_client):
    image_id, _ = _make_image_with_file(filename="rt_test6.svs")
    resp = anon_client.post(f"/images/{image_id}/analyze")
    assert resp.status_code in (401, 403)


# --- Test del servicio -------------------------------------------------------

def test_run_full_analysis_composes_tissue_and_density(client):
    """El resumen combina las métricas de tejido y de densidad."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    image_id, file_path = _make_image_with_file(filename="rt_test7.svs")
    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
    db = sessionmaker(bind=engine)()
    try:
        analysis = analysis_service.run_full_analysis(
            db, image_id, file_path, grid_size=30, colormap="hot"
        )
        assert analysis.analysis_type == "full_analysis"
        summary = analysis.result_data
        assert summary["density"]["colormap"] == "hot"
        assert summary["tissue"]["tissue_percent"] is not None
        assert summary["density"]["density_mean"] is not None
    finally:
        db.close()
