"""
Tests del servicio de analíticas y del endpoint GET /images/:id/analytics.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.image import Image
from app.models.analysis import AnalysisResult, DensityMap
from app.services.analysis import analytics_service


def _session():
    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
    return sessionmaker(bind=engine)()


def _make_image(filename="analytics_test.svs", user_id=1, width=1000, height=800):
    db = _session()
    try:
        image = Image(
            filename=filename,
            file_path=f"/tmp/{filename}",
            user_id=user_id,
            width=width,
            height=height,
            level_count=1,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image.id
    finally:
        db.close()


# --- Tests unitarios del servicio --------------------------------------------

def test_centroid_rectangle():
    assert analytics_service._centroid(
        "rectangle", {"x": 10, "y": 20, "width": 100, "height": 40}
    ) == (60.0, 40.0)


def test_centroid_circle():
    assert analytics_service._centroid(
        "circle", {"x": 5, "y": 7, "radius": 3}
    ) == (5.0, 7.0)


def test_centroid_polygon():
    c = analytics_service._centroid(
        "polygon", {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
    )
    assert c == (5.0, 5.0)


def test_centroid_invalid_returns_none():
    assert analytics_service._centroid("rectangle", {}) is None


def test_spatial_grid_counts_centroids():
    class _Ann:
        def __init__(self, st, coords):
            self.shape_type = st
            self.coordinates = coords

    anns = [
        _Ann("circle", {"x": 5, "y": 5, "radius": 1}),     # celda (0,0)
        _Ann("circle", {"x": 92, "y": 92, "radius": 1}),   # celda (9,9)
        _Ann("circle", {"x": 95, "y": 95, "radius": 1}),   # celda (9,9)
    ]
    grid = analytics_service._spatial_grid(anns, 100, 100, bins=10)
    assert grid["bins"] == 10
    assert grid["grid"][0][0] == 1
    assert grid["grid"][9][9] == 2
    assert grid["max"] == 2


# --- Tests de endpoint -------------------------------------------------------

def _create_class(client, name, color="#FF0000"):
    resp = client.post(
        "/annotation-classes", json={"name": name, "color": color}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_annotation(client, image_id, payload):
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_analytics_empty_image(client):
    image_id = _make_image(filename="analytics_empty.svs")
    resp = client.get(f"/images/{image_id}/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_annotations"] == 0
    assert data["by_type"] == []
    assert data["by_class"] == []
    assert data["tissue"] is None
    assert data["density_zones"] is None
    assert data["spatial"]["bins"] == 10


def test_analytics_with_annotations(client):
    image_id = _make_image(filename="analytics_ann.svs")
    class_id = _create_class(client, "Tumor", "#8e2de2")

    _create_annotation(client, image_id, {
        "shape_type": "rectangle",
        "coordinates": {"x": 10, "y": 10, "width": 20, "height": 20},
        "color": "#8e2de2",
        "class_id": class_id,
    })
    _create_annotation(client, image_id, {
        "shape_type": "circle",
        "coordinates": {"x": 500, "y": 400, "radius": 15},
        "color": "#b24592",
    })
    _create_annotation(client, image_id, {
        "shape_type": "rectangle",
        "coordinates": {"x": 900, "y": 700, "width": 10, "height": 10},
        "color": "#b24592",
    })

    resp = client.get(f"/images/{image_id}/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_annotations"] == 3

    by_type = {row["type"]: row["count"] for row in data["by_type"]}
    assert by_type["rectangle"] == 2
    assert by_type["circle"] == 1

    by_class = {row["class"]: row["count"] for row in data["by_class"]}
    assert by_class["Tumor"] == 1
    assert by_class["Sin clasificar"] == 2

    # La tabla de distribución combina tipo + clase.
    assert any(
        r["type"] == "rectangle" and r["class"] == "Tumor" and r["count"] == 1
        for r in data["distribution"]
    )
    assert data["spatial"]["max"] >= 1


def test_analytics_includes_tissue_and_density(client):
    image_id = _make_image(filename="analytics_full.svs")
    db = _session()
    try:
        db.add(AnalysisResult(
            image_id=image_id,
            analysis_type="tissue_mask",
            result_data={"tissue_percent": 42.5, "width": 100, "height": 80,
                         "method": "otsu_saturation_intensity"},
        ))
        db.add(DensityMap(
            image_id=image_id,
            grid_size=256,
            density_data={
                "colormap": "viridis",
                "density_mean": 0.4,
                "density_max": 0.9,
                "density_std": 0.2,
                "matrix": [[0.0, 0.5], [1.0, 0.25]],
            },
        ))
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/images/{image_id}/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tissue"]["tissue_percent"] == 42.5
    dz = data["density_zones"]
    assert dz["grid_size"] == 256
    assert dz["rows"] == 2 and dz["cols"] == 2
    assert len(dz["row_means"]) == 2
    assert len(dz["col_means"]) == 2
    assert sum(dz["histogram"]["counts"]) == 4


def test_analytics_invalid_bins(client):
    image_id = _make_image(filename="analytics_bins.svs")
    resp = client.get(f"/images/{image_id}/analytics", params={"spatial_bins": 1})
    assert resp.status_code == 422


def test_analytics_image_not_found(client):
    resp = client.get("/images/99999/analytics")
    assert resp.status_code == 404


def test_analytics_requires_auth(anon_client):
    image_id = _make_image(filename="analytics_auth.svs")
    resp = anon_client.get(f"/images/{image_id}/analytics")
    assert resp.status_code in (401, 403)
