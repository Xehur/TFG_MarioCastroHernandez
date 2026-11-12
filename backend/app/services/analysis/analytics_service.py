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
- Métricas legibles: superficie de tejido y fragmentos en mm², reparto de
  densidad baja/media/alta, información física de la imagen y resumen de la
  clasificación IA ya calculada (si existe; aquí no se ejecuta).

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


def _tissue_stats_from_result(
    result: Optional[AnalysisResult], mpp: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Extrae las estadísticas de tejido de un AnalysisResult (o None).

    Con ``mpp`` (µm/px de nivel 0) añade la superficie de tejido y la de cada
    fragmento en mm², a partir de la miniatura y su escala.
    """
    if result is None:
        return None
    data = result.result_data or {}
    stats: Dict[str, Any] = {
        "tissue_percent": data.get("tissue_percent"),
        "width": data.get("width"),
        "height": data.get("height"),
        "method": data.get("method"),
        "fragments": data.get("fragments"),
        "area_mm2": None,
        "fragment_areas_mm2": [],
    }
    scale = data.get("scale")
    width, height = data.get("width") or 0, data.get("height") or 0
    if mpp and scale and width and height and data.get("tissue_percent") is not None:
        px_mm2 = px_area_mm2(1, scale, mpp)
        stats["area_mm2"] = round(
            width * height * data["tissue_percent"] / 100.0 * px_mm2, 3
        )
        stats["fragment_areas_mm2"] = [
            round(a * px_mm2, 3) for a in (data.get("fragment_areas_px") or [])[:10]
        ]
    return stats


def _tissue_stats(db: Session, image_id: int) -> Optional[Dict[str, Any]]:
    result = (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.annotation_id.is_(None),
            AnalysisResult.analysis_type == TISSUE_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    return _tissue_stats_from_result(result)


def _density_zones_from_map(
    density: Optional[DensityMap], histogram_bins: int
) -> Optional[Dict[str, Any]]:
    """Calcula medias por fila/columna e histograma de un DensityMap (o None)."""
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


def _density_zones(
    db: Session, image_id: int, histogram_bins: int
) -> Optional[Dict[str, Any]]:
    density = (
        db.query(DensityMap)
        .filter(
            DensityMap.image_id == image_id,
            DensityMap.annotation_id.is_(None),
        )
        .order_by(DensityMap.created_at.desc())
        .first()
    )
    return _density_zones_from_map(density, histogram_bins)


# --- Métricas físicas y resúmenes legibles -----------------------------------

_MAGNIFICATIONS = (2.5, 5, 10, 20, 40, 60, 80)
CARCINOMA_CODES = ("INSITU", "INVASIVE")


def image_mpp(properties: Optional[Dict[str, Any]]) -> Optional[float]:
    """µm/px de nivel 0 según los metadatos de la WSI (``openslide.mpp-x``)."""
    try:
        value = float((properties or {}).get("openslide.mpp-x"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def magnification(mpp: Optional[float]) -> Optional[float]:
    """Aumento aproximado del escáner (0,25 µm/px ≈ 40x; 0,5 µm/px ≈ 20x)."""
    if not mpp:
        return None
    return min(_MAGNIFICATIONS, key=lambda m: abs(m - 10.0 / mpp))


def px_area_mm2(px: float, scale: float, mpp: float) -> float:
    """Área en mm² de ``px`` píxeles de una miniatura de escala ``scale``."""
    side_mm = scale * mpp / 1000.0
    return px * side_mm * side_mm


def image_info(width: int, height: int, mpp: Optional[float]) -> Dict[str, Any]:
    """Tamaño en píxeles y físico de la imagen (o región) analizada."""
    return {
        "width_px": width,
        "height_px": height,
        "mpp": round(mpp, 4) if mpp else None,
        "width_mm": round(width * mpp / 1000.0, 2) if mpp else None,
        "height_mm": round(height * mpp / 1000.0, 2) if mpp else None,
        "magnification": magnification(mpp),
    }


def annotation_area_px(shape_type: str, coords: Dict[str, Any]) -> float:
    """Área de una anotación en píxeles de nivel 0."""
    try:
        if shape_type == "rectangle":
            return abs(float(coords["width"]) * float(coords["height"]))
        if shape_type == "circle":
            r = float(coords.get("radius") or 0.0)
            return 3.141592653589793 * r * r
        if shape_type == "polygon":
            pts = coords.get("points") or []
            if len(pts) < 3:
                return 0.0
            acc = 0.0
            for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
                acc += float(x1) * float(y2) - float(x2) * float(y1)
            return abs(acc) / 2.0
    except (KeyError, TypeError, ValueError):
        return 0.0
    return 0.0


def density_levels(density: Optional[DensityMap]) -> Optional[Dict[str, Any]]:
    """Reparto de las zonas con tejido en densidad baja (< 33 %), media y alta
    (> 66 %), más fácil de leer que un histograma."""
    if density is None:
        return None
    matrix = (density.density_data or {}).get("matrix")
    if not matrix:
        return None
    values = [v for row in matrix for v in row if v and v > 0]
    total = len(values)
    low = sum(1 for v in values if v < 1 / 3)
    high = sum(1 for v in values if v > 2 / 3)
    medium = total - low - high

    def pct(n: int) -> float:
        return round(100.0 * n / total, 1) if total else 0.0

    return {
        "zones": total,
        "levels": [
            {"level": "Baja", "range": "< 33 %", "count": low, "percent": pct(low)},
            {"level": "Media", "range": "33-66 %", "count": medium, "percent": pct(medium)},
            {"level": "Alta", "range": "> 66 %", "count": high, "percent": pct(high)},
        ],
        "mean_percent": round(100.0 * sum(values) / total, 1) if total else 0.0,
    }


def ai_summary(
    analysis: Optional[AnalysisResult], tissue_area_mm2: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Resumen legible de una clasificación IA ya calculada (no la ejecuta)."""
    from app.services.analysis import ai_classification_service as ai  # import diferido

    if analysis is None or not ai._is_current_model(analysis):
        return None
    data = analysis.result_data or {}
    analyzed = data.get("tissue_patches") or 0
    out_classes = []
    for c in data.get("classes") or []:
        area = (
            round(tissue_area_mm2 * c.get("percent", 0) / 100.0, 3)
            if tissue_area_mm2 is not None
            else None
        )
        out_classes.append(
            {
                "code": c.get("code"),
                "name": c.get("name"),
                "color": c.get("color"),
                "count": c.get("count", 0),
                "percent": c.get("percent", 0.0),
                "area_mm2": area,
            }
        )
    dominant = next(
        (c for c in out_classes if c["code"] == data.get("dominant_class")), None
    )
    sampling = data.get("sampling") or {}
    return {
        "analyzed_fields": analyzed,
        "tissue_fields": sampling.get("tissue_cells") or analyzed,
        "dominant_class": dominant["code"] if dominant else None,
        "dominant_name": dominant["name"] if dominant else None,
        "dominant_percent": dominant["percent"] if dominant else None,
        "carcinoma_percent": round(
            sum(c["percent"] for c in out_classes if c["code"] in CARCINOMA_CODES), 1
        ),
        "mean_confidence": data.get("mean_confidence"),
        "classes": out_classes,
        "model": (data.get("model") or {}).get("dataset"),
        "field_um": sampling.get("field_um"),
        "disclaimer": data.get("disclaimer"),
    }


def build_analytics(
    db: Session,
    image_id: int,
    width: int,
    height: int,
    spatial_bins: int = DEFAULT_SPATIAL_BINS,
    histogram_bins: int = DEFAULT_HISTOGRAM_BINS,
    mpp: Optional[float] = None,
) -> Dict[str, Any]:
    """Compone el conjunto completo de analíticas de una imagen."""
    from app.services.analysis import ai_classification_service as ai  # import diferido

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

    # Área anotada por clase (mm²), si se conoce la resolución física.
    annotated_mm2: Optional[float] = None
    if mpp:
        px_to_mm2 = (mpp / 1000.0) ** 2
        area_by_class: Dict[str, float] = {}
        for ann in annotations:
            cls = class_map.get(ann.class_id) if ann.class_id else None
            name = cls.name if cls else _UNCLASSIFIED
            area = annotation_area_px(ann.shape_type, ann.coordinates or {}) * px_to_mm2
            area_by_class[name] = area_by_class.get(name, 0.0) + area
        for row in breakdowns["by_class"]:
            row["area_mm2"] = round(area_by_class.get(row["class"], 0.0), 3)
        annotated_mm2 = round(sum(area_by_class.values()), 3)

    tissue_result = (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.image_id == image_id,
            AnalysisResult.annotation_id.is_(None),
            AnalysisResult.analysis_type == TISSUE_ANALYSIS_TYPE,
        )
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )
    tissue = _tissue_stats_from_result(tissue_result, mpp)
    density = (
        db.query(DensityMap)
        .filter(DensityMap.image_id == image_id, DensityMap.annotation_id.is_(None))
        .order_by(DensityMap.created_at.desc())
        .first()
    )

    return {
        "image_id": image_id,
        "total_annotations": len(annotations),
        "annotated_area_mm2": annotated_mm2,
        "by_type": breakdowns["by_type"],
        "by_class": breakdowns["by_class"],
        "distribution": breakdowns["distribution"],
        "spatial": _spatial_grid(annotations, width, height, spatial_bins),
        "tissue": tissue,
        "density_zones": _density_zones_from_map(density, histogram_bins),
        "density_levels": density_levels(density),
        "image_info": image_info(width, height, mpp),
        "ai": ai_summary(
            ai.get_cached_image_classification(db, image_id),
            tissue["area_mm2"] if tissue else None,
        ),
    }
