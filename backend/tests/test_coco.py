"""
Tests para exportación e importación de anotaciones en formato COCO.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.image import Image
from app.services import coco_service


def _make_image(filename="coco_test.svs", user_id=1):
    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        image = Image(
            filename=filename,
            file_path=f"/tmp/{filename}",
            user_id=user_id,
            width=1000,
            height=800,
            level_count=3,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image.id
    finally:
        db.close()


@pytest.fixture
def image_id(client):
    return _make_image()


def _create_annotation(client, image_id, payload):
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Tests unitarios del servicio (sin BD) -----------------------------------

def test_rectangle_geometry():
    seg, bbox, area = coco_service._shape_to_coco_geometry(
        "rectangle", {"x": 10, "y": 20, "width": 100, "height": 50}
    )
    assert bbox == [10, 20, 100, 50]
    assert area == 5000
    assert seg[0] == [10, 20]
    assert seg[2] == [110, 70]


def test_circle_geometry():
    seg, bbox, area = coco_service._shape_to_coco_geometry(
        "circle", {"x": 50, "y": 50, "radius": 10}
    )
    assert bbox == [40, 40, 20, 20]
    assert round(area, 2) == round(3.141592653589793 * 100, 2)
    assert len(seg) == coco_service._CIRCLE_SEGMENTS


def test_polygon_geometry():
    seg, bbox, area = coco_service._shape_to_coco_geometry(
        "polygon", {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
    )
    assert bbox == [0, 0, 10, 10]
    assert area == 100.0


def test_validate_coco_missing_key():
    with pytest.raises(coco_service.COCOValidationError):
        coco_service.validate_coco({"images": [], "annotations": []})


def test_validate_coco_not_dict():
    with pytest.raises(coco_service.COCOValidationError):
        coco_service.validate_coco([])


def test_parse_coco_polygon_deduction():
    data = {
        "images": [{"id": 1, "file_name": "a.svs", "width": 10, "height": 10}],
        "categories": [{"id": 1, "name": "Tumor"}],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "segmentation": [[0, 0, 10, 0, 10, 10, 0, 10]],
                "bbox": [0, 0, 10, 10],
            }
        ],
    }
    coco_service.validate_coco(data)
    parsed = coco_service.parse_coco(data)
    assert parsed[0]["shape_type"] == "polygon"
    assert parsed[0]["class_name"] == "Tumor"


def test_parse_coco_bbox_only_rectangle():
    data = {
        "images": [{"id": 1, "file_name": "a.svs", "width": 10, "height": 10}],
        "categories": [{"id": 1, "name": "unclassified"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [5, 5, 20, 30]}
        ],
    }
    parsed = coco_service.parse_coco(data)
    assert parsed[0]["shape_type"] == "rectangle"
    assert parsed[0]["coordinates"] == {"x": 5, "y": 5, "width": 20, "height": 30}
    assert parsed[0]["class_name"] is None


def test_parse_coco_category_mapping():
    data = {
        "images": [{"id": 1, "file_name": "a.svs", "width": 10, "height": 10}],
        "categories": [{"id": 1, "name": "cell"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [0, 0, 5, 5]}
        ],
    }
    parsed = coco_service.parse_coco(data, category_mapping={"cell": "Célula"})
    assert parsed[0]["class_name"] == "Célula"


# --- Tests de endpoints ------------------------------------------------------

def test_export_coco_empty(client, image_id):
    resp = client.get(f"/images/{image_id}/export/coco")
    assert resp.status_code == 200
    data = resp.json()
    assert data["images"][0]["id"] == image_id
    assert data["annotations"] == []
    assert data["categories"] == []
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_export_coco_image_not_found(client):
    resp = client.get("/images/99999/export/coco")
    assert resp.status_code == 404


def test_export_coco_with_annotations(client, image_id):
    _create_annotation(
        client,
        image_id,
        {
            "shape_type": "rectangle",
            "coordinates": {"x": 10, "y": 20, "width": 100, "height": 50},
            "label": "Zona A",
            "color": "#00FF00",
        },
    )
    _create_annotation(
        client,
        image_id,
        {
            "shape_type": "polygon",
            "coordinates": {"points": [[0, 0], [10, 0], [5, 10]]},
            "color": "#FF0000",
        },
    )
    resp = client.get(f"/images/{image_id}/export/coco")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["annotations"]) == 2
    ann = data["annotations"][0]
    assert ann["bbox"] == [10, 20, 100, 50]
    assert ann["attributes"]["shape_type"] == "rectangle"
    assert ann["attributes"]["color"] == "#00FF00"
    # Sin clase -> categoría "unclassified"
    assert data["categories"][0]["name"] == "unclassified"


def test_export_coco_with_class(client, image_id):
    cls = client.post(
        "/annotation-classes", json={"name": "Tumor", "color": "#123456"}
    ).json()
    _create_annotation(
        client,
        image_id,
        {
            "shape_type": "circle",
            "coordinates": {"x": 50, "y": 50, "radius": 10},
            "class_id": cls["id"],
            "color": "#123456",
        },
    )
    resp = client.get(f"/images/{image_id}/export/coco")
    data = resp.json()
    assert data["categories"][0]["name"] == "Tumor"
    assert data["annotations"][0]["category_id"] == data["categories"][0]["id"]


def test_import_coco_creates_annotations(client, image_id):
    coco = {
        "images": [
            {"id": 1, "file_name": "x.svs", "width": 1000, "height": 800}
        ],
        "categories": [{"id": 1, "name": "Necrosis", "color": "#abcdef"}],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [5, 5, 20, 30],
                "segmentation": [[5, 5, 25, 5, 25, 35, 5, 35]],
                "attributes": {
                    "shape_type": "rectangle",
                    "color": "#abcdef",
                    "label": "L1",
                },
            }
        ],
    }
    resp = client.post(f"/images/{image_id}/import/coco", json={"coco": coco})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported"] == 1
    assert "Necrosis" in data["created_classes"]
    assert data["items"][0]["shape_type"] == "rectangle"

    # Verificar que quedaron persistidas.
    listed = client.get(f"/images/{image_id}/annotations").json()
    assert listed["total"] == 1


def test_import_coco_invalid(client, image_id):
    resp = client.post(
        f"/images/{image_id}/import/coco",
        json={"coco": {"images": []}},
    )
    assert resp.status_code == 422


def test_import_coco_image_not_found(client):
    resp = client.post(
        "/images/99999/import/coco",
        json={"coco": {"images": [], "annotations": [], "categories": []}},
    )
    assert resp.status_code == 404


def test_import_coco_with_category_mapping(client, image_id):
    coco = {
        "images": [{"id": 1, "file_name": "x.svs", "width": 10, "height": 10}],
        "categories": [{"id": 1, "name": "cell"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [0, 0, 5, 5]}
        ],
    }
    resp = client.post(
        f"/images/{image_id}/import/coco",
        json={"coco": coco, "category_mapping": {"cell": "Célula"}},
    )
    assert resp.status_code == 200
    classes = client.get("/annotation-classes").json()
    assert any(c["name"] == "Célula" for c in classes)


def test_coco_round_trip(client, image_id):
    """Exportar e importar debe reconstruir las mismas formas."""
    cls = client.post(
        "/annotation-classes", json={"name": "Estroma", "color": "#0000FF"}
    ).json()
    _create_annotation(
        client,
        image_id,
        {
            "shape_type": "circle",
            "coordinates": {"x": 100, "y": 100, "radius": 25},
            "class_id": cls["id"],
            "color": "#0000FF",
            "label": "C1",
        },
    )
    exported = client.get(f"/images/{image_id}/export/coco").json()

    image2 = _make_image(filename="coco_test2.svs")
    resp = client.post(
        f"/images/{image2}/import/coco", json={"coco": exported}
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["shape_type"] == "circle"
    assert item["coordinates"]["radius"] == 25
    assert item["coordinates"]["x"] == 100
    assert item["label"] == "C1"


def test_import_requires_auth(anon_client, image_id):
    resp = anon_client.post(
        f"/images/{image_id}/import/coco",
        json={"coco": {"images": [], "annotations": [], "categories": []}},
    )
    assert resp.status_code in (401, 403)
