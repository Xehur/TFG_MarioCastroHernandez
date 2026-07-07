"""
Detección de tejido vs. fondo en imágenes histológicas (Sprint 6, issue 30).

Estrategia (CV clásico, sin IA):
- El fondo de un WSI suele ser blanco/gris muy claro y con baja saturación,
  mientras que el tejido teñido (H&E, etc.) tiene mayor saturación y es más
  oscuro. Combinamos ambos criterios:
    1. Umbral de Otsu sobre el canal de saturación (HSV).
    2. Umbral de Otsu sobre la intensidad (escala de grises): el tejido es
       más oscuro que el fondo claro.
- Se limpia la máscara con morfología: cierre, relleno de huecos y
  eliminación de objetos pequeños (ruido).

Diseño extensible: ``TissueDetector`` define la interfaz ``detect`` y
``ClassicalTissueDetector`` (Otsu) es la implementación por defecto. Los
endpoints usan siempre ``detect_tissue`` / ``get_tissue_detector`` sin conocer
la implementación concreta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import numpy as np
from skimage.color import rgb2hsv, rgb2gray
from skimage.filters import threshold_otsu
from skimage.morphology import (
    remove_small_objects,
    remove_small_holes,
    closing,
    disk,
)


@dataclass
class TissueDetectionResult:
    """Resultado de la detección de tejido."""

    mask: np.ndarray  # máscara binaria booleana (H, W)
    tissue_percent: float  # % de píxeles clasificados como tejido
    threshold_saturation: Optional[float]
    threshold_intensity: Optional[float]
    width: int
    height: int
    extra: Dict[str, Any] = field(default_factory=dict)

    def stats(self) -> Dict[str, Any]:
        """Métricas serializables (sin la máscara) para guardar en BD."""
        return {
            "tissue_percent": round(self.tissue_percent, 4),
            "threshold_saturation": self.threshold_saturation,
            "threshold_intensity": self.threshold_intensity,
            "width": self.width,
            "height": self.height,
            **self.extra,
        }


class TissueDetector:
    """Interfaz de un detector de tejido."""

    def detect(self, rgb: np.ndarray) -> TissueDetectionResult:  # pragma: no cover
        raise NotImplementedError


def _to_rgb_float(rgb: np.ndarray) -> np.ndarray:
    """Normaliza una imagen RGB a float en [0, 1] y descarta canal alfa."""
    if rgb.ndim == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
    if rgb.shape[-1] == 4:
        rgb = rgb[..., :3]
    if rgb.dtype != np.float64 and rgb.dtype != np.float32:
        rgb = rgb.astype(np.float64) / 255.0
    else:
        # Si viene en [0,255] float, normalizar
        if rgb.max() > 1.0:
            rgb = rgb / 255.0
    return rgb


class ClassicalTissueDetector(TissueDetector):
    """
    Detector clásico basado en Otsu (saturación + intensidad) y morfología.

    Args:
        min_object_size: tamaño mínimo (px) de una región de tejido; regiones
            más pequeñas se eliminan como ruido.
        min_hole_size: tamaño máximo (px) de un hueco interior que se rellena.
        closing_radius: radio del elemento estructurante para el cierre.
    """

    def __init__(
        self,
        min_object_size: int = 64,
        min_hole_size: int = 64,
        closing_radius: int = 2,
    ):
        self.min_object_size = min_object_size
        self.min_hole_size = min_hole_size
        self.closing_radius = closing_radius

    def detect(self, rgb: np.ndarray) -> TissueDetectionResult:
        rgb = _to_rgb_float(rgb)
        height, width = rgb.shape[0], rgb.shape[1]

        hsv = rgb2hsv(rgb)
        saturation = hsv[..., 1]
        gray = rgb2gray(rgb)

        thresh_sat: Optional[float] = None
        thresh_int: Optional[float] = None

        # Umbral de saturación: el tejido tiñe con más color que el fondo.
        if float(saturation.max() - saturation.min()) > 1e-6:
            thresh_sat = float(threshold_otsu(saturation))
            mask_sat = saturation > thresh_sat
        else:
            mask_sat = np.zeros((height, width), dtype=bool)

        # Umbral de intensidad: el tejido es más oscuro que el fondo claro.
        if float(gray.max() - gray.min()) > 1e-6:
            thresh_int = float(threshold_otsu(gray))
            mask_int = gray < thresh_int
        else:
            mask_int = np.zeros((height, width), dtype=bool)

        # Un píxel es tejido si tiene color o si es notablemente oscuro.
        mask = mask_sat | mask_int

        mask = self._clean_mask(mask)

        tissue_percent = float(mask.mean() * 100.0) if mask.size else 0.0

        return TissueDetectionResult(
            mask=mask,
            tissue_percent=tissue_percent,
            threshold_saturation=thresh_sat,
            threshold_intensity=thresh_int,
            width=width,
            height=height,
            extra={"method": "otsu_saturation_intensity"},
        )

    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        if not mask.any():
            return mask
        if self.closing_radius > 0:
            mask = closing(mask, disk(self.closing_radius))
        if self.min_hole_size > 0:
            mask = remove_small_holes(mask, self.min_hole_size)
        if self.min_object_size > 0:
            mask = remove_small_objects(mask, self.min_object_size)
        return mask


_default_detector = ClassicalTissueDetector()


def get_tissue_detector() -> TissueDetector:
    """
    Devuelve el detector de tejido activo (clásico, basado en Otsu).

    Punto único de sustitución: los endpoints usan siempre ``detect_tissue`` /
    ``get_tissue_detector`` sin conocer la implementación concreta.
    """
    return _default_detector


def detect_tissue(rgb: np.ndarray) -> TissueDetectionResult:
    """Atajo que usa el detector activo."""
    return get_tissue_detector().detect(rgb)


def mask_to_rgba_overlay(
    mask: np.ndarray,
    color: tuple[int, int, int] = (34, 197, 94),
    alpha: int = 128,
) -> np.ndarray:
    """
    Convierte una máscara booleana en una imagen RGBA (H, W, 4) uint8 con el
    tejido coloreado y semitransparente, y el fondo totalmente transparente.
    """
    height, width = mask.shape
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    overlay[mask, 0] = color[0]
    overlay[mask, 1] = color[1]
    overlay[mask, 2] = color[2]
    overlay[mask, 3] = alpha
    return overlay
