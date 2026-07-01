"""
Servicio de analíticas de imagen (Sprint 6, issue 46).

Genera, a partir de las anotaciones de una imagen y de los análisis de tejido /
densidad ya calculados, un conjunto de datos listos para representar en gráficas
y tablas en el frontend (Chart.js/Recharts/Plotly):

- Distribución de anotaciones (tabla y totales).
- Anotaciones por tipo de forma (para gráfica de barras).
- Anotaciones por clasificación (para gráfica de tarta).
- Distribución espacial de los centroides (heatmap por celdas).
- Estadísticas de tejido (si existe análisis).
- Densidad por zonas: medias por fila/columna e histograma (si existe mapa).

No ejecuta análisis pesados: solo agrega datos existentes, por lo que es rápido
y seguro de llamar en tiempo real.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.annotation import Annotation, AnnotationClass
from app.models.analysis import AnalysisResult, DensityMap
from app.services.analysis.tissue_service import TISSUE_ANALYSIS_TYPE

logger = logging.getLogger(__name__)

DEFAULT_SPATIAL_BINS = 10
DEFAULT_HISTOGRAM_BINS = 10
_UNCLASSIFIED = "Sin clasificar"


def _centroid(shape_type: str, coords: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Centro aproximado de una forma en píxeles de imagen."""
    try:
        if shape_type == "rectangle":
            return (
                float(coords["x"]) + float(coords["width"]) / 2.0,
                float(coords["y"]) + float(coords["height"]) / 2.0,
            )
        if shape_type == "circle":
            return float(coords["x"]), float(coords["y"])
        if shape_type == "polygon":
            points = coords.get("points") or []
            if not points:
                return None
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            return sum(xs) / len(xs), sum(ys) / len(ys)
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return None


def _spatial_grid(
    annotations: List[Annotation],
    width: int,
    height: int,
    bins: int,
) -> Dict[str, Any]:
    """Cuenta los centroides de las anotaciones en una rejilla bins x bins."""
    grid = [[0 for _ in range(bins)] for _ in range(bins)]
    if width <= 0 or height <= 0:
        return {"bins": bins, "grid": grid, "max": 0}

    cell_w = width / bins
    cell_h = height / bins
    max_count = 0
    for ann in annotations:
        centroid = _centroid(ann.shape_type, ann.coordinates or {})
        if centroid is None:
            continue
        cx, cy = centroid
        col = min(bins - 1, max(0, int(cx / cell_w))) if cell_w else 0
        row = min(bins - 1, max(0, int(cy / cell_h))) if cell_h else 0
        grid[row][col] += 1
        max_count = max(max_count, grid[row][col])

    return {"bins": bins, "width": width, "height": height, "grid": grid, "max": max_count}


def _annotation_breakdowns(
    annotations: List[Annotation],
    class_map: Dict[int, AnnotationClass],
) -> Dict[str, Any]:
    """Recuentos por tipo de forma y por clasificación, y tabla combinada."""
    by_type: Dict[str, int] = {}
    by_class: Dict[str, int] = {}
    class_colors: Dict[str, str] = {}
    combined: Dict[Tuple[str, str], int] = {}

    for ann in annotations:
        by_type[ann.shape_type] = by_type.get(ann.shape_type, 0) + 1

        if ann.class_id and ann.class_id in class_map:
            cls = class_map[ann.class_id]
            class_name = cls.name
            class_colors.setdefault(class_name, cls.color)
        else:
            class_name = _UNCLASSIFIED
            class_colors.setdefault(class_name, "#9ca3af")

        by_class[class_name] = by_class.get(class_name, 0) + 1
        key = (ann.shape_type, class_name)
        combined[key] = combined.get(key, 0) + 1

    by_type_list = [
        {"type": t, "count": c} for t, c in sorted(by_type.items())
    ]
    by_class_list = [
        {"class": name, "count": c, "color": class_colors.get(name, "#9ca3af")}
        for name, c in sorted(by_class.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    table = [
        {"type": t, "class": name, "count": c}
        for (t, name), c in sorted(combined.items())
    ]
    return {
        "by_type": by_type_list,
        "by_class": by_class_list,
        "distribution": table,
    }


def _tissue_stats(db: Session, image_id: int) -> Optional[Dict[str, Any]]:
    result = (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.analysis_type == TISSUE_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    if result is None:
        return None
    data = result.result_data or {}
    return {
        "tissue_percent": data.get("tissue_percent"),
        "width": data.get("width"),
        "height": data.get("height"),
        "method": data.get("method"),
    }


def _density_zones(
    db: Session, image_id: int, histogram_bins: int
) -> Optional[Dict[str, Any]]:
    density = (
        db.query(DensityMap)
        .filter(DensityMap.image_id == image_id)
        .order_by(DensityMap.created_at.desc())
        .first()
    )
    if density is None:
        return None
    data = density.density_data or {}
    matrix = data.get("matrix")
    if not matrix:
        return None

    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0

    row_means = [sum(r) / len(r) if r else 0.0 for r in matrix]
    col_means = []
    for c in range(cols):
        column = [matrix[r][c] for r in range(rows)]
        col_means.append(sum(column) / len(column) if column else 0.0)

    # Histograma de todas las densidades de celda en [0, 1].
    counts = [0 for _ in range(histogram_bins)]
    flat = [v for r in matrix for v in r]
    for v in flat:
        idx = min(histogram_bins - 1, max(0, int(v * histogram_bins)))
        counts[idx] += 1
    edges = [round(i / histogram_bins, 3) for i in range(histogram_bins + 1)]

    return {
        "grid_size": density.grid_size,
        "colormap": data.get("colormap"),
        "rows": rows,
        "cols": cols,
        "row_means": [round(v, 6) for v in row_means],
        "col_means": [round(v, 6) for v in col_means],
        "density_mean": data.get("density_mean"),
        "density_max": data.get("density_max"),
        "density_std": data.get("density_std"),
        "histogram": {"edges": edges, "counts": counts},
    }


def build_analytics(
    db: Session,
    image_id: int,
    width: int,
    height: int,
    spatial_bins: int = DEFAULT_SPATIAL_BINS,
    histogram_bins: int = DEFAULT_HISTOGRAM_BINS,
) -> Dict[str, Any]:
    """Compone el conjunto completo de analíticas de una imagen."""
    annotations = (
        db.query(Annotation).filter(Annotation.image_id == image_id).all()
    )
    class_ids = {a.class_id for a in annotations if a.class_id}
    class_map: Dict[int, AnnotationClass] = {}
    if class_ids:
        classes = (
            db.query(AnnotationClass)
            .filter(AnnotationClass.id.in_(class_ids))
            .all()
        )
        class_map = {c.id: c for c in classes}

    breakdowns = _annotation_breakdowns(annotations, class_map)

    return {
        "image_id": image_id,
        "total_annotations": len(annotations),
        "by_type": breakdowns["by_type"],
        "by_class": breakdowns["by_class"],
        "distribution": breakdowns["distribution"],
        "spatial": _spatial_grid(annotations, width, height, spatial_bins),
        "tissue": _tissue_stats(db, image_id),
        "density_zones": _density_zones(db, image_id, histogram_bins),
    }
