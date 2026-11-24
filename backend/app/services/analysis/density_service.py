"""
Servicio de alto nivel para la generación del mapa de densidades de una WSI.

Orquesta: lectura de miniatura (OpenSlide) -> detección de tejido ->
cálculo de densidad por celdas del grid -> cacheado del PNG del heatmap en
disco y de la matriz/metadatos en BD (tabla ``density_maps``).

El cacheado se indexa por (image_id, grid_size, colormap): distintos tamaños
de grid o colormaps producen registros distintos.
"""
import os
import logging
from typing import Optional

from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import DensityMap
from app.services.wsi.openslide_service import OpenSlideService
from app.services.analysis import tissue_service
from app.services.analysis.tissue_detection import (
    detect_tissue,
    DETECTOR_VERSION,
    is_current_detector,
)
from app.services.analysis.density_generation import (
    generate_density_map,
    density_to_heatmap_rgba,
    _colormap_lut,
    DEFAULT_COLORMAP,
)

logger = logging.getLogger(__name__)

_THUMBNAIL_MAX_SIZE = 2048
DEFAULT_GRID_SIZE = 256


def _analysis_dir(image_id: int) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "analysis", str(image_id))
    os.makedirs(path, exist_ok=True)
    return path


def _heatmap_png_path(image_id: int, grid_size: int, colormap: str) -> str:
    return os.path.join(
        _analysis_dir(image_id), f"density_{grid_size}_{colormap}.png"
    )


def generate_density(
    db: Session,
    image_id: int,
    file_path: str,
    grid_size: int = DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    max_size: int = _THUMBNAIL_MAX_SIZE,
    *,
    rgb=None,
    scale: Optional[float] = None,
    tissue=None,
) -> DensityMap:
    """
    Ejecuta la generación del mapa de densidades, guarda el PNG del heatmap y
    persiste (o actualiza) el registro DensityMap con la matriz y metadatos.

    ``rgb``/``scale``/``tissue`` opcionales permiten reutilizar una miniatura y
    una detección ya calculadas (p.ej. en el análisis consolidado).
    """
    if rgb is None or scale is None:
        slide = OpenSlideService(file_path)
        try:
            rgb, scale = slide.get_thumbnail_rgb(max_size=max_size)
        finally:
            slide.close()

    factor = tissue_service.get_threshold_factor(db, image_id)
    tissue = (
        tissue if tissue is not None
        else detect_tissue(rgb, threshold_factor=factor)
    )
    base_width = int(round(tissue.width * scale))
    base_height = int(round(tissue.height * scale))

    result = generate_density_map(
        tissue.mask,
        grid_size=grid_size,
        base_width=base_width,
        base_height=base_height,
        colormap=colormap,
    )

    heatmap = density_to_heatmap_rgba(
        result.density,
        out_shape=(tissue.height, tissue.width),
        colormap=colormap,
    )
    png_path = _heatmap_png_path(image_id, grid_size, colormap)
    PILImage.fromarray(heatmap, mode="RGBA").save(png_path, format="PNG")

    data = result.stats()
    data["scale"] = scale
    data["map_path"] = png_path
    data["thumbnail_max_size"] = max_size
    data["tissue_percent"] = round(tissue.tissue_percent, 4)
    data["detector_mode"] = "classical"
    data["detector_version"] = DETECTOR_VERSION
    data["threshold_factor"] = tissue.extra.get("threshold_factor", factor)
    # Paradas de color (RGB 0-255) para dibujar el colorbar en el frontend.
    data["colorbar"] = _colormap_lut(colormap, samples=16)

    existing = _exact_cached(db, image_id, grid_size, colormap)
    if existing is not None:
        existing.density_data = data
        db.commit()
        db.refresh(existing)
        return existing

    density_map = DensityMap(
        image_id=image_id,
        grid_size=grid_size,
        density_data=data,
    )
    db.add(density_map)
    db.commit()
    db.refresh(density_map)
    return density_map


def _exact_cached(
    db: Session, image_id: int, grid_size: int, colormap: str
) -> Optional[DensityMap]:
    """Busca en Python el registro con el colormap exacto (portable a SQLite)."""
    candidates = (
        db.query(DensityMap)
        .filter(
            DensityMap.image_id == image_id,
            DensityMap.annotation_id.is_(None),
            DensityMap.grid_size == grid_size,
        )
        .order_by(DensityMap.created_at.desc())
        .all()
    )
    for candidate in candidates:
        if (candidate.density_data or {}).get("colormap") == colormap:
            return candidate
    return None


def get_or_create_density(
    db: Session,
    image_id: int,
    file_path: str,
    grid_size: int = DEFAULT_GRID_SIZE,
    colormap: str = DEFAULT_COLORMAP,
    force: bool = False,
) -> DensityMap:
    """
    Devuelve el mapa cacheado si existe (y el PNG está en disco) o lo genera.
    Con ``force=True`` siempre regenera.
    """
    if not force:
        cached = _exact_cached(db, image_id, grid_size, colormap)
        if cached is not None:
            data = cached.density_data or {}
            map_path = data.get("map_path")
            # Regenera mapas derivados del antiguo detector de IA para curarlos.
            mode_ok = data.get("detector_mode") == "classical" and is_current_detector(
                data, tissue_service.get_threshold_factor(db, image_id)
            )
            if map_path and os.path.exists(map_path) and mode_ok:
                return cached
    return generate_density(db, image_id, file_path, grid_size, colormap)


def load_heatmap_png_bytes(density_map: DensityMap) -> bytes:
    """Lee los bytes del PNG del heatmap desde disco."""
    map_path = (density_map.density_data or {}).get("map_path")
    if not map_path or not os.path.exists(map_path):
        raise FileNotFoundError("PNG de mapa de densidad no encontrado")
    with open(map_path, "rb") as fh:
        return fh.read()
