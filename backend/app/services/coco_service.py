"""
Servicio de conversión entre el modelo de anotaciones interno y el formato
COCO (Common Objects in Context) JSON.

El formato COCO estándar se compone de:
- info: metadatos del dataset
- images: [{id, file_name, width, height}]
- annotations: [{id, image_id, category_id, segmentation, area, bbox, iscrowd}]
- categories: [{id, name, supercategory}]

Mapeo de formas internas -> COCO:
- rectangle {x, y, width, height}      -> bbox = [x, y, w, h], segmentation = 4 esquinas
- circle    {x, y, radius}             -> bbox = [x-r, y-r, 2r, 2r], segmentation = polígono
- polygon   {points: [[x, y], ...]}    -> bbox = min/max, segmentation = puntos aplanados

Para permitir un round-trip sin pérdida (exportar e importar recuperando la
forma original exacta), cada anotación COCO incluye un campo extra
``attributes`` con ``shape_type``, ``color`` y ``label``. Este campo es una
extensión permitida por el formato y las herramientas COCO estándar lo ignoran.
"""
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Número de vértices para aproximar un círculo como polígono COCO.
_CIRCLE_SEGMENTS = 32

_UNCLASSIFIED = "unclassified"


# --- Utilidades geométricas --------------------------------------------------

def _polygon_area(points: List[List[float]]) -> float:
    """Área de un polígono (fórmula del cordón / shoelace)."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _polygon_bbox(points: List[List[float]]) -> List[float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_min, y_min = min(xs), min(ys)
    return [x_min, y_min, max(xs) - x_min, max(ys) - y_min]


def _circle_to_points(cx: float, cy: float, r: float) -> List[List[float]]:
    pts = []
    for i in range(_CIRCLE_SEGMENTS):
        theta = 2.0 * math.pi * i / _CIRCLE_SEGMENTS
        pts.append([cx + r * math.cos(theta), cy + r * math.sin(theta)])
    return pts


# --- Export: interno -> COCO -------------------------------------------------

def _shape_to_coco_geometry(
    shape_type: str, coords: Dict[str, Any]
) -> Tuple[List[List[float]], List[float], float]:
    """Devuelve (segmentation, bbox, area) en formato COCO para una forma."""
    if shape_type == "rectangle":
        x, y = float(coords["x"]), float(coords["y"])
        w, h = float(coords["width"]), float(coords["height"])
        seg = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
        return seg, [x, y, w, h], w * h

    if shape_type == "circle":
        cx, cy = float(coords["x"]), float(coords["y"])
        r = float(coords["radius"])
        seg = _circle_to_points(cx, cy, r)
        return seg, [cx - r, cy - r, 2 * r, 2 * r], math.pi * r * r

    if shape_type == "polygon":
        pts = [[float(p[0]), float(p[1])] for p in coords["points"]]
        return pts, _polygon_bbox(pts), _polygon_area(pts)

    raise ValueError(f"shape_type no soportado: {shape_type}")


def build_coco(
    image: Any,
    annotations: List[Any],
    classes_by_id: Dict[int, Any],
) -> Dict[str, Any]:
    """
    Construye un diccionario COCO a partir de una imagen y sus anotaciones.

    Args:
        image: modelo Image (id, filename, width, height).
        annotations: lista de modelos Annotation.
        classes_by_id: dict {class_id: AnnotationClass} para resolver categorías.
    """
    # Construir categorías a partir de las clases referenciadas y de un
    # comodín "unclassified" para anotaciones sin clase.
    categories: List[Dict[str, Any]] = []
    category_id_by_key: Dict[str, int] = {}

    def _ensure_category(name: str, color: Optional[str]) -> int:
        if name not in category_id_by_key:
            new_id = len(category_id_by_key) + 1
            category_id_by_key[name] = new_id
            categories.append(
                {
                    "id": new_id,
                    "name": name,
                    "supercategory": "annotation",
                    "color": color,
                }
            )
        return category_id_by_key[name]

    coco_annotations: List[Dict[str, Any]] = []
    for ann in annotations:
        cls = classes_by_id.get(ann.class_id) if ann.class_id else None
        cat_name = cls.name if cls else _UNCLASSIFIED
        cat_color = cls.color if cls else None
        category_id = _ensure_category(cat_name, cat_color)

        seg, bbox, area = _shape_to_coco_geometry(ann.shape_type, ann.coordinates)
        flat_seg = [coord for point in seg for coord in point]

        coco_annotations.append(
            {
                "id": ann.id,
                "image_id": image.id,
                "category_id": category_id,
                "segmentation": [flat_seg],
                "area": area,
                "bbox": bbox,
                "iscrowd": 0,
                # Extensión propia para round-trip sin pérdida.
                "attributes": {
                    "shape_type": ann.shape_type,
                    "color": ann.color,
                    "label": ann.label,
                },
            }
        )

    return {
        "info": {
            "description": f"WSI Viewer export - image {image.id}",
            "version": "1.0",
            "date_created": datetime.utcnow().isoformat(),
        },
        "licenses": [],
        "images": [
            {
                "id": image.id,
                "file_name": image.filename,
                "width": image.width,
                "height": image.height,
            }
        ],
        "annotations": coco_annotations,
        "categories": categories,
    }


# --- Import: COCO -> interno -------------------------------------------------

class COCOValidationError(ValueError):
    """Error de validación de un documento COCO."""


def validate_coco(data: Any) -> None:
    """Valida la estructura mínima de un documento COCO. Lanza COCOValidationError."""
    if not isinstance(data, dict):
        raise COCOValidationError("El documento COCO debe ser un objeto JSON")
    for key in ("images", "annotations", "categories"):
        if key not in data:
            raise COCOValidationError(f"Falta la clave obligatoria '{key}'")
        if not isinstance(data[key], list):
            raise COCOValidationError(f"'{key}' debe ser una lista")

    for cat in data["categories"]:
        if not isinstance(cat, dict) or "id" not in cat or "name" not in cat:
            raise COCOValidationError("cada categoría requiere 'id' y 'name'")

    for ann in data["annotations"]:
        if not isinstance(ann, dict):
            raise COCOValidationError("cada anotación debe ser un objeto")
        if "category_id" not in ann:
            raise COCOValidationError("cada anotación requiere 'category_id'")
        if "segmentation" not in ann and "bbox" not in ann:
            raise COCOValidationError(
                "cada anotación requiere 'segmentation' o 'bbox'"
            )


def _flat_to_points(flat: List[float]) -> List[List[float]]:
    return [[flat[i], flat[i + 1]] for i in range(0, len(flat) - 1, 2)]


def _coco_annotation_to_shape(ann: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Convierte una anotación COCO a (shape_type, coordinates) internos.

    Prioriza el campo ``attributes.shape_type`` (round-trip sin pérdida). Si no
    existe, deduce la forma: usa segmentation -> polygon, o bbox -> rectangle.
    """
    attributes = ann.get("attributes") or {}
    forced_shape = attributes.get("shape_type")

    segmentation = ann.get("segmentation")
    seg_points: Optional[List[List[float]]] = None
    if isinstance(segmentation, list) and segmentation:
        first = segmentation[0]
        if isinstance(first, list) and len(first) >= 6:
            seg_points = _flat_to_points(first)

    bbox = ann.get("bbox")

    if forced_shape == "circle" and bbox:
        x, y, w, h = bbox
        r = max(w, h) / 2.0
        return "circle", {"x": x + w / 2.0, "y": y + h / 2.0, "radius": r}

    if forced_shape == "rectangle" and bbox:
        x, y, w, h = bbox
        return "rectangle", {"x": x, "y": y, "width": w, "height": h}

    if forced_shape == "polygon" and seg_points:
        return "polygon", {"points": seg_points}

    # Deducción sin atributos: segmentation -> polygon, si no bbox -> rectangle.
    if seg_points and len(seg_points) >= 3:
        return "polygon", {"points": seg_points}

    if bbox:
        x, y, w, h = bbox
        return "rectangle", {"x": x, "y": y, "width": w, "height": h}

    raise COCOValidationError(
        f"No se pudo convertir la anotación COCO id={ann.get('id')}"
    )


def parse_coco(
    data: Dict[str, Any],
    category_mapping: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Convierte un documento COCO validado en una lista de anotaciones internas.

    Args:
        data: documento COCO (ya validado).
        category_mapping: dict opcional {nombre_categoria_coco: nombre_clase_destino}
            para renombrar categorías durante la importación.

    Devuelve una lista de dicts con: shape_type, coordinates, label, color,
    class_name (nombre de clase destino, o None si "unclassified").
    """
    category_mapping = category_mapping or {}
    cat_name_by_id = {c["id"]: c["name"] for c in data["categories"]}
    cat_color_by_id = {c["id"]: c.get("color") for c in data["categories"]}

    result: List[Dict[str, Any]] = []
    for ann in data["annotations"]:
        shape_type, coords = _coco_annotation_to_shape(ann)

        attributes = ann.get("attributes") or {}
        raw_cat_name = cat_name_by_id.get(ann["category_id"], _UNCLASSIFIED)
        mapped_name = category_mapping.get(raw_cat_name, raw_cat_name)
        class_name = None if mapped_name == _UNCLASSIFIED else mapped_name

        color = attributes.get("color") or cat_color_by_id.get(
            ann["category_id"]
        ) or "#FF0000"
        label = attributes.get("label")

        result.append(
            {
                "shape_type": shape_type,
                "coordinates": coords,
                "label": label,
                "color": color,
                "class_name": class_name,
            }
        )
    return result
