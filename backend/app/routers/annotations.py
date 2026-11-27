"""
Router para CRUD de anotaciones y clases de anotación.

Endpoints:
- POST   /images/{image_id}/annotations   crear anotación
- GET    /images/{image_id}/annotations   listar anotaciones de una imagen
- PUT    /annotations/{annotation_id}      actualizar (solo propietario)
- DELETE /annotations/{annotation_id}      eliminar (solo propietario)
- GET    /annotation-classes               listar clases del usuario
- POST   /annotation-classes               crear clase
- DELETE /annotation-classes/{class_id}    eliminar clase (solo propietario)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.access import get_owned_image_or_404
from app.models.user import User
from app.models.image import Image
from app.models.annotation import Annotation, AnnotationClass
from app.schemas.annotation import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationListResponse,
    AnnotationClassCreate,
    AnnotationClassResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["annotations"])


def _get_owned_class_or_404(db: Session, class_id: int, user: User) -> AnnotationClass:
    cls = db.query(AnnotationClass).filter(AnnotationClass.id == class_id).first()
    if cls is None:
        raise HTTPException(status_code=404, detail="Clase de anotación no encontrada")
    if cls.user_id != user.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    return cls


# --- Clases de anotación -----------------------------------------------------

@router.get("/annotation-classes", response_model=list[AnnotationClassResponse])
def list_annotation_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(AnnotationClass)
        .filter(AnnotationClass.user_id == current_user.id)
        .order_by(AnnotationClass.name)
        .all()
    )


@router.post(
    "/annotation-classes",
    response_model=AnnotationClassResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation_class(
    payload: AnnotationClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cls = AnnotationClass(
        name=payload.name,
        color=payload.color,
        description=payload.description,
        user_id=current_user.id,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


@router.delete("/annotation-classes/{class_id}")
def delete_annotation_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cls = _get_owned_class_or_404(db, class_id, current_user)
    db.delete(cls)
    db.commit()
    return {"message": "Clase eliminada correctamente"}


# --- Anotaciones -------------------------------------------------------------

@router.post(
    "/images/{image_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    image_id: int,
    payload: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_image_or_404(db, image_id, current_user)

    if payload.class_id is not None:
        _get_owned_class_or_404(db, payload.class_id, current_user)

    annotation = Annotation(
        image_id=image_id,
        user_id=current_user.id,
        shape_type=payload.shape_type.value,
        coordinates=payload.coordinates,
        label=payload.label,
        color=payload.color,
        class_id=payload.class_id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


@router.get(
    "/images/{image_id}/annotations",
    response_model=AnnotationListResponse,
)
def list_annotations(
    image_id: int,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_image_or_404(db, image_id, current_user)

    query = db.query(Annotation).filter(Annotation.image_id == image_id)
    total = query.count()
    items = (
        query.order_by(Annotation.created_at).offset(skip).limit(limit).all()
    )
    return {"total": total, "items": items}


def _get_owned_annotation_or_404(
    db: Session, annotation_id: int, user: User
) -> Annotation:
    annotation = (
        db.query(Annotation).filter(Annotation.id == annotation_id).first()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="Anotación no encontrada")
    if annotation.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="No autorizado para modificar esta anotación"
        )
    return annotation


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotation = _get_owned_annotation_or_404(db, annotation_id, current_user)

    data = payload.model_dump(exclude_unset=True)

    if data.get("class_id") is not None:
        _get_owned_class_or_404(db, data["class_id"], current_user)

    if "shape_type" in data and data["shape_type"] is not None:
        annotation.shape_type = data["shape_type"].value
    if "coordinates" in data and data["coordinates"] is not None:
        annotation.coordinates = data["coordinates"]
    if "label" in data:
        annotation.label = data["label"]
    if "color" in data and data["color"] is not None:
        annotation.color = data["color"]
    if "class_id" in data:
        annotation.class_id = data["class_id"]

    db.commit()
    db.refresh(annotation)
    return annotation


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotation = _get_owned_annotation_or_404(db, annotation_id, current_user)
    db.delete(annotation)
    db.commit()
    return {"message": "Anotación eliminada correctamente"}
