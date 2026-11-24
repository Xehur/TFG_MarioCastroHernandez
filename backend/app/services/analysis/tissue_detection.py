"""
Detección de tejido vs. fondo en imágenes histológicas (CV clásico, sin IA).

Estrategia (densidad óptica + umbral con histéresis):
1. Se estima el color del cristal (fondo) como el percentil 99 de cada canal
   y se calcula la densidad óptica (OD) de cada píxel respecto a él:
   ``OD = -log10(I / I_fondo)``. El cristal tiene OD ≈ 0 y cualquier tinción,
   aunque sea pálida, OD > 0.
2. Umbral FUERTE: Otsu sobre la OD (tejido claramente teñido).
3. Umbral DÉBIL: justo por encima del ruido del fondo (mediana + 6·MAD de la
   OD del fondo, mínimo 0.035) o un mínimo de saturación de color.
4. Histéresis: se conservan las regiones débiles conectadas a alguna región
   fuerte. Así se recupera el tejido pálido (grasa, estroma laxo, eosina
   clara) que un único umbral de Otsu dejaba fuera, sin aceptar manchas
   aisladas del cristal.
5. Artefactos: se excluye la tinta de rotulador (tonos verde/azul-verdoso/
   amarillo, fuera de la gama H&E), incluidas sus zonas pálidas, y las franjas
   finas pegadas al borde de la imagen (sombras del escáner).
6. Limpieza morfológica: cierre, relleno de huecos interiores (vacuolas de
   grasa) y eliminación de objetos pequeños, con tamaños relativos al área.

Diseño extensible: ``TissueDetector`` define la interfaz ``detect`` y
``ClassicalTissueDetector`` es la implementación por defecto. Los endpoints
usan siempre ``detect_tissue`` / ``get_tissue_detector`` sin conocer la
implementación concreta. ``DETECTOR_VERSION`` se guarda con cada resultado
para regenerar las cachés cuando cambia el algoritmo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import numpy as np
from scipy import ndimage as ndi
from skimage.color import rgb2hsv
from skimage.filters import threshold_otsu
from skimage.morphology import (
    remove_small_objects,
    remove_small_holes,
    closing,
    disk,
)


DETECTOR_METHOD = "od_hysteresis"
DETECTOR_VERSION = "od-hysteresis-v2"

# Factor de umbral ajustable por el usuario: multiplica los umbrales que el
# detector calcula automáticamente. 1.0 = detección automática; < 1 detecta más
# tejido (umbral más bajo) y > 1, menos.
DEFAULT_THRESHOLD_FACTOR = 1.0
MIN_THRESHOLD_FACTOR = 0.25
MAX_THRESHOLD_FACTOR = 3.0


def clamp_threshold_factor(value: Optional[float]) -> float:
    """Normaliza el factor de umbral al rango admitido (None -> 1.0)."""
    if value is None:
        return DEFAULT_THRESHOLD_FACTOR
    return round(
        float(min(MAX_THRESHOLD_FACTOR, max(MIN_THRESHOLD_FACTOR, value))), 3
    )


def is_current_detector(
    data: Optional[Dict[str, Any]], threshold_factor: float = DEFAULT_THRESHOLD_FACTOR
) -> bool:
    """True si un resultado cacheado se generó con el detector actual y el
    mismo factor de umbral."""
    if not data or data.get("detector_version") != DETECTOR_VERSION:
        return False
    stored = data.get("threshold_factor", DEFAULT_THRESHOLD_FACTOR)
    return abs(float(stored) - float(threshold_factor)) < 1e-6


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

    def detect(
        self, rgb: np.ndarray, threshold_factor: float = DEFAULT_THRESHOLD_FACTOR
    ) -> TissueDetectionResult:  # pragma: no cover
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
    Detector clásico por densidad óptica con umbral de histéresis.

    Args:
        min_object_frac: tamaño mínimo de una región de tejido, como fracción
            del área de la imagen (mínimo absoluto ``min_object_size`` px).
        min_hole_frac: tamaño máximo de un hueco interior que se rellena, como
            fracción del área (mínimo absoluto ``min_hole_size`` px).
        min_object_size, min_hole_size: mínimos absolutos en píxeles.
        closing_radius: radio del cierre morfológico final.
        weak_sat: saturación mínima que, por sí sola, marca un píxel como
            candidato débil a tejido.
        od_floor: OD mínima del umbral débil (evita aceptar ruido del cristal).
        noise_k: múltiplo del MAD del fondo para el umbral débil.
    """

    # Tinta de rotulador: tonos fuera de la gama H&E (rosa/morado/azul-morado).
    PEN_HUE_RANGE = (0.17, 0.58)  # amarillo -> verde -> cian
    PEN_MIN_SAT = 0.12
    PEN_MIN_OD = 0.08

    def __init__(
        self,
        min_object_size: int = 64,
        min_hole_size: int = 64,
        closing_radius: int = 3,
        min_object_frac: float = 0.0002,
        min_hole_frac: float = 0.002,
        weak_sat: float = 0.08,
        od_floor: float = 0.035,
        noise_k: float = 6.0,
    ):
        self.min_object_size = min_object_size
        self.min_hole_size = min_hole_size
        self.closing_radius = closing_radius
        self.min_object_frac = min_object_frac
        self.min_hole_frac = min_hole_frac
        self.weak_sat = weak_sat
        self.od_floor = od_floor
        self.noise_k = noise_k

    def detect(
        self, rgb: np.ndarray, threshold_factor: float = DEFAULT_THRESHOLD_FACTOR
    ) -> TissueDetectionResult:
        """Detecta el tejido. ``threshold_factor`` escala los umbrales
        automáticos (fuerte, débil y de saturación) para que el usuario pueda
        hacer la detección más o menos estricta."""
        factor = clamp_threshold_factor(threshold_factor)
        rgb = _to_rgb_float(rgb)
        height, width = rgb.shape[0], rgb.shape[1]
        empty = np.zeros((height, width), dtype=bool)

        hsv = rgb2hsv(rgb)
        hue, sat = hsv[..., 0], hsv[..., 1]

        # 1) Densidad óptica respecto al color del cristal. El suelo de 0.85
        #    evita tomar tejido como "fondo" en regiones casi sin cristal.
        background = np.clip(
            np.percentile(rgb.reshape(-1, 3), 99, axis=0), 0.85, 1.0
        )
        # OD máxima entre canales (el tejido rosa pálido absorbe sobre especialmente en
        # un canal). Ojo a la precedencia: primero -log10, después max.
        od = (-np.log10(np.clip(rgb / background, 1e-3, 1.0))).max(axis=-1)

        # 2) Tinta de rotulador (se excluye siempre).
        pen = (
            (hue > self.PEN_HUE_RANGE[0])
            & (hue < self.PEN_HUE_RANGE[1])
            & (sat > self.PEN_MIN_SAT)
            & (od > self.PEN_MIN_OD)
        )
        if pen.any():
            pen = ndi.binary_dilation(pen, iterations=2)

        # 3) Umbrales fuerte (Otsu) y débil (ruido del fondo).
        valid = od[~pen]
        if valid.size == 0 or float(np.ptp(valid)) < 1e-6:
            return self._result(empty, None, None, width, height, background, pen, factor)
        # Otsu sobre la OD recortada: unos pocos píxeles extremos (polvo,
        # restos de tinta) no deben desplazar el umbral.
        t_auto = float(threshold_otsu(np.minimum(valid, np.percentile(valid, 99.5))))
        bg = od[(od < t_auto) & ~pen]
        med = float(np.median(bg)) if bg.size else 0.0
        mad = float(np.median(np.abs(bg - med))) if bg.size else 0.0
        t_high = t_auto * factor
        t_low = min(max(med + self.noise_k * 1.4826 * mad, self.od_floor) * factor, t_high)

        strong = (od > t_high) & ~pen
        weak = ((od > t_low) | (sat > self.weak_sat * factor)) & ~pen

        # 4) Histéresis: regiones débiles conectadas a alguna región fuerte.
        weak = closing(weak, disk(2))
        labels, n = ndi.label(weak)
        keep = np.zeros(n + 1, dtype=bool)
        keep[np.unique(labels[strong])] = True
        keep[0] = False
        mask = keep[labels]

        # 5-6) Limpieza y artefactos.
        mask = _drop_border_bands(mask)
        mask &= ~pen
        mask = _drop_ink_components(mask, hue, sat)
        mask = self._clean_mask(mask)
        return self._result(mask, t_high, t_low, width, height, background, pen, factor)

    def _result(self, mask, t_high, t_low, width, height, background, pen, factor):
        tissue_percent = float(mask.mean() * 100.0) if mask.size else 0.0
        return TissueDetectionResult(
            mask=mask,
            tissue_percent=tissue_percent,
            threshold_saturation=self.weak_sat,
            threshold_intensity=None,
            width=width,
            height=height,
            extra={
                "method": DETECTOR_METHOD,
                "detector_version": DETECTOR_VERSION,
                "threshold_factor": factor,
                "od_threshold_high": None if t_high is None else round(t_high, 4),
                "od_threshold_low": None if t_low is None else round(t_low, 4),
                "background_rgb": [int(round(v * 255)) for v in background],
                "pen_ink_percent": round(float(pen.mean() * 100.0), 4),
                **_fragment_stats(mask),
            },
        )

    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        if not mask.any():
            return mask
        area = mask.size
        if self.closing_radius > 0:
            mask = closing(mask, disk(self.closing_radius))
        # scikit-image 0.26 sustituye area_threshold/min_size por max_size. Con la
        # versión fijada en requirements.txt, el parámetro antiguo ya se trataba
        # como max_size (elimina tamaños <= umbral), así que el resultado es el mismo.
        hole = max(self.min_hole_size, int(area * self.min_hole_frac))
        if hole > 0:
            mask = remove_small_holes(mask, max_size=hole)
        obj = max(self.min_object_size, int(area * self.min_object_frac))
        if obj > 0:
            mask = remove_small_objects(mask, max_size=obj)
        return mask


def _drop_border_bands(
    mask: np.ndarray,
    min_coverage: float = 0.6,
    max_thickness: float = 0.05,
    contrast: float = 0.5,
) -> np.ndarray:
    """Elimina franjas finas pegadas a un borde de la imagen (sombras o bordes
    del escáner), aunque toquen el tejido.

    Para cada borde se cuentan las filas/columnas consecutivas cubiertas en más
    de ``min_coverage``. Solo es una franja si es fina (``max_thickness`` del
    lado) y justo después la cobertura cae claramente (< ``contrast`` veces).
    Así una región toda de tejido (p. ej. una anotación dentro del tejido) no
    se recorta.
    """
    if not mask.any():
        return mask
    out = mask.copy()
    for axis in (0, 1):
        cover = mask.mean(axis=1 - axis)  # cobertura por fila (0) o columna (1)
        n = cover.size
        limit = max(1, int(n * max_thickness))
        for reverse in (False, True):
            seq = cover[::-1] if reverse else cover
            k = 0
            while k < limit and seq[k] > min_coverage:
                k += 1
            if k == 0 or k >= limit:
                continue
            after = seq[k + 2 : k + 2 + max(k, 3)]
            band_cov = float(seq[:k].mean())
            if after.size and float(after.mean()) < contrast * band_cov:
                # Zona de la franja (con margen para su borde difuso). En ella
                # solo se conserva el tejido que continúa justo a continuación
                # (p. ej. la punta de un cilindro que entra en la franja).
                cut = min(n - 1, 2 * k + 2)
                idx = slice(n - cut, n) if reverse else slice(0, cut)
                nxt = n - cut - 1 if reverse else cut
                if axis == 0:
                    out[idx, :] &= mask[nxt, :][None, :]
                else:
                    out[:, idx] &= mask[:, nxt][:, None]
    return out


def _drop_ink_components(
    mask: np.ndarray, hue: np.ndarray, sat: np.ndarray, max_ink_frac: float = 0.3
) -> np.ndarray:
    """Descarta regiones cuyo color es mayoritariamente de tinta de rotulador
    (tonos amarillo-verde-cian, también en sus zonas pálidas)."""
    if not mask.any():
        return mask
    lo, hi = ClassicalTissueDetector.PEN_HUE_RANGE
    ink_like = (hue > lo) & (hue < hi) & (sat > 0.04)
    labels, n = ndi.label(mask)
    if n == 0:
        return mask
    idx = np.arange(1, n + 1)
    ink_frac = ndi.mean(ink_like.astype(np.float64), labels, idx)
    drop = np.zeros(n + 1, dtype=bool)
    drop[1:] = np.asarray(ink_frac) > max_ink_frac
    return mask & ~drop[labels]


def _fragment_stats(mask: np.ndarray, top: int = 50) -> Dict[str, Any]:
    """Nº de fragmentos de tejido (regiones conexas) y sus áreas en píxeles
    de la miniatura (de mayor a menor, como mucho ``top``)."""
    if not mask.any():
        return {"fragments": 0, "fragment_areas_px": []}
    labels, n = ndi.label(mask)
    areas = np.bincount(labels.ravel())[1:]
    areas = sorted((int(a) for a in areas), reverse=True)
    return {"fragments": int(n), "fragment_areas_px": areas[:top]}


_default_detector = ClassicalTissueDetector()


def get_tissue_detector() -> TissueDetector:
    """
    Devuelve el detector de tejido activo (clásico, OD + histéresis).

    Punto único de sustitución: los endpoints usan siempre ``detect_tissue`` /
    ``get_tissue_detector`` sin conocer la implementación concreta.
    """
    return _default_detector


def detect_tissue(
    rgb: np.ndarray, threshold_factor: float = DEFAULT_THRESHOLD_FACTOR
) -> TissueDetectionResult:
    """Atajo que usa el detector activo."""
    return get_tissue_detector().detect(rgb, threshold_factor=threshold_factor)


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
