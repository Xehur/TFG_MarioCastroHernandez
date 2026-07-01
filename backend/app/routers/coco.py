"""
Router para exportación e importación de anotaciones en formato COCO.

Endpoints:
- GET  /images/{image_id}/export/coco   exporta anotaciones como COCO JSON
- POST /images/{image_id}/import/coco    importa anotaciones desde COCO JSON
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.image import Image
from app.models.annotation import Annotation, AnnotationClass
from app.schemas.annotation import COCOImportRequest, COCOImportResponse
from app.services import coco_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["coco"])


def _get_image_or_404(db: Session, image_id: int) -> Image:
    image = db.query(Image).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return image


@router.get("/images/{image_id}/export/coco")
def export_coco(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta las anotaciones de una imagen en formato COCO JSON."""
    image = _get_image_or_404(db, image_id)

    annotations = (
        db.query(Annotation)
        .filter(Annotation.image_id == image_id)
        .order_by(Annotation.id)
        .all()
    )

    class_ids = {a.class_id for a in annotations if a.class_id is not None}
    classes_by_id = {}
    if class_ids:
        classes = (
            db.query(AnnotationClass)
            .filter(AnnotationClass.id.in_(class_ids))
            .all()
        )
        classes_by_id = {c.id: c for c in classes}

    coco = coco_service.build_coco(image, annotations, classes_by_id)

    filename = f"image_{image_id}_coco.json"
    return JSONResponse(
        content=coco,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/images/{image_id}/import/coco",
    response_model=COCOImportResponse,
)
def import_coco(
    image_id: int,
    payload: COCOImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Importa anotaciones desde un documento COCO a una imagen."""
    image = _get_image_or_404(db, image_id)

    try:
        coco_service.validate_coco(payload.coco)
    except coco_service.COCOValidationError as exc:
        raise HTTPException(status_code=422, detail=f"COCO inválido: {exc}")

    try:
        parsed = coco_service.parse_coco(payload.coco, payload.category_mapping)
    except coco_service.COCOValidationError as exc:
        raise HTTPException(status_code=422, detail=f"COCO inválido: {exc}")

    # Cache de clases del usuario por nombre (para mapear/crear).
    existing_classes = (
        db.query(AnnotationClass)
        .filter(AnnotationClass.user_id == current_user.id)
        .all()
    )
    class_by_name = {c.name: c for c in existing_classes}
    created_classes: list[str] = []

    created_annotations: list[Annotation] = []
    for item in parsed:
        class_id = None
        class_name = item["class_name"]
        if class_name:
            cls = class_by_name.get(class_name)
            if cls is None:
                cls = AnnotationClass(
                    name=class_name,
                    color=item["color"],
                    user_id=current_user.id,
                )
                db.add(cls)
                db.flush()
                class_by_name[class_name] = cls
                created_classes.append(class_name)
            class_id = cls.id

        annotation = Annotation(
            image_id=image.id,
            user_id=current_user.id,
            shape_type=item["shape_type"],
            coordinates=item["coordinates"],
            label=item["label"],
            color=item["color"],
            class_id=class_id,
        )
        db.add(annotation)
        created_annotations.append(annotation)

    db.commit()
    for ann in created_annotations:
        db.refresh(ann)

    return {
        "imported": len(created_annotations),
        "created_classes": created_classes,
        "items": created_annotations,
    }
