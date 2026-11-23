"""
Tests para los endpoints de anotaciones y clases de anotación.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.image import Image


def _make_image(filename="ann_test.svs", user_id=1):
    """Inserta una imagen directamente en la BD de test y devuelve su id."""
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
    """Crea una imagen de prueba (client garantiza que la BD existe)."""
    return _make_image()


@pytest.fixture
def rectangle_payload():
    return {
        "shape_type": "rectangle",
        "coordinates": {"x": 10, "y": 20, "width": 100, "height": 50},
        "label": "Zona A",
        "color": "#FF0000",
    }


# --- Creación ----------------------------------------------------------------

def test_create_rectangle_annotation(client, image_id, rectangle_payload):
    resp = client.post(f"/images/{image_id}/annotations", json=rectangle_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["shape_type"] == "rectangle"
    assert data["coordinates"]["width"] == 100
    assert data["label"] == "Zona A"
    assert data["image_id"] == image_id
    assert "id" in data


def test_create_circle_annotation(client, image_id):
    payload = {
        "shape_type": "circle",
        "coordinates": {"x": 50, "y": 50, "radius": 25},
        "color": "#00FF00",
    }
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["coordinates"]["radius"] == 25


def test_create_polygon_annotation(client, image_id):
    payload = {
        "shape_type": "polygon",
        "coordinates": {"points": [[0, 0], [10, 0], [5, 10]]},
        "color": "#0000FF",
    }
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201
    assert len(resp.json()["coordinates"]["points"]) == 3


def test_create_annotation_invalid_rectangle(client, image_id):
    payload = {
        "shape_type": "rectangle",
        "coordinates": {"x": 10, "y": 20},  # falta width/height
    }
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 422


def test_create_polygon_too_few_points(client, image_id):
    payload = {
        "shape_type": "polygon",
        "coordinates": {"points": [[0, 0], [10, 0]]},
    }
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 422


def test_create_annotation_invalid_shape_type(client, image_id):
    payload = {"shape_type": "triangle", "coordinates": {}}
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 422


def test_create_annotation_image_not_found(client, rectangle_payload):
    resp = client.post("/images/99999/annotations", json=rectangle_payload)
    assert resp.status_code == 404


def test_create_annotation_requires_auth(anon_client, image_id, rectangle_payload):
    resp = anon_client.post(f"/images/{image_id}/annotations", json=rectangle_payload)
    assert resp.status_code == 401


# --- Listado -----------------------------------------------------------------

def test_list_annotations_empty(client, image_id):
    resp = client.get(f"/images/{image_id}/annotations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_annotations(client, image_id, rectangle_payload):
    client.post(f"/images/{image_id}/annotations", json=rectangle_payload)
    client.post(f"/images/{image_id}/annotations", json=rectangle_payload)
    resp = client.get(f"/images/{image_id}/annotations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_annotations_pagination(client, image_id, rectangle_payload):
    for _ in range(3):
        client.post(f"/images/{image_id}/annotations", json=rectangle_payload)
    resp = client.get(f"/images/{image_id}/annotations?skip=1&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1


def test_list_annotations_image_not_found(client):
    resp = client.get("/images/99999/annotations")
    assert resp.status_code == 404


# --- Actualización -----------------------------------------------------------

def test_update_annotation(client, image_id, rectangle_payload):
    created = client.post(
        f"/images/{image_id}/annotations", json=rectangle_payload
    ).json()
    resp = client.put(
        f"/annotations/{created['id']}",
        json={"label": "Modificado", "color": "#123456"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Modificado"
    assert data["color"] == "#123456"


def test_update_annotation_not_found(client):
    resp = client.put("/annotations/99999", json={"label": "x"})
    assert resp.status_code == 404


def test_update_annotation_other_user_forbidden(
    client, anon_client, image_id, rectangle_payload
):
    created = client.post(
        f"/images/{image_id}/annotations", json=rectangle_payload
    ).json()

    # Segundo usuario
    anon_client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "otherpass1", "full_name": "Otro"},
    )
    login = anon_client.post(
        "/auth/login", json={"email": "other@example.com", "password": "otherpass1"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    resp = anon_client.put(
        f"/annotations/{created['id']}", json={"label": "hack"}, headers=headers
    )
    assert resp.status_code == 403


# --- Eliminación -------------------------------------------------------------

def test_delete_annotation(client, image_id, rectangle_payload):
    created = client.post(
        f"/images/{image_id}/annotations", json=rectangle_payload
    ).json()
    resp = client.delete(f"/annotations/{created['id']}")
    assert resp.status_code == 200

    # Ya no aparece en el listado
    listed = client.get(f"/images/{image_id}/annotations").json()
    assert listed["total"] == 0


def test_delete_annotation_not_found(client):
    resp = client.delete("/annotations/99999")
    assert resp.status_code == 404


# --- Clases de anotación -----------------------------------------------------

def test_create_and_list_annotation_class(client):
    resp = client.post(
        "/annotation-classes",
        json={"name": "Tumor", "color": "#FF0000", "description": "Tejido tumoral"},
    )
    assert resp.status_code == 201
    cls = resp.json()
    assert cls["name"] == "Tumor"

    listed = client.get("/annotation-classes")
    assert listed.status_code == 200
    assert any(c["name"] == "Tumor" for c in listed.json())


def test_create_annotation_with_class(client, image_id):
    cls = client.post(
        "/annotation-classes", json={"name": "Necrosis", "color": "#00FF00"}
    ).json()
    payload = {
        "shape_type": "rectangle",
        "coordinates": {"x": 0, "y": 0, "width": 10, "height": 10},
        "class_id": cls["id"],
    }
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["class_id"] == cls["id"]


def test_create_annotation_with_invalid_class(client, image_id):
    payload = {
        "shape_type": "rectangle",
        "coordinates": {"x": 0, "y": 0, "width": 10, "height": 10},
        "class_id": 99999,
    }
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 404


def test_delete_annotation_class(client):
    cls = client.post(
        "/annotation-classes", json={"name": "Temporal", "color": "#999999"}
    ).json()
    resp = client.delete(f"/annotation-classes/{cls['id']}")
    assert resp.status_code == 200


def test_annotation_classes_require_auth(anon_client):
    resp = anon_client.get("/annotation-classes")
    assert resp.status_code == 401
