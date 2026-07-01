"""
Generación de mapas de densidad de tejido (Sprint 6, issue 31).

Estrategia (CV clásico, sin IA):
- Se parte de la máscara binaria de tejido (ver ``tissue_detection``).
- La imagen se divide en un grid configurable de celdas cuadradas cuyo tamaño
  se expresa en píxeles de la imagen base (``grid_size``).
- Para cada celda se calcula la densidad de tejido = fracción de píxeles de la
  celda clasificados como tejido (valor en [0, 1]).
- La matriz de densidades se colorea con un ``colormap`` (viridis, hot, ...)
  para generar un heatmap RGBA semitransparente alineado con la imagen base.

Diseño extensible: ``DensityGenerator`` define la interfaz ``generate``. La
implementación por defecto es ``ClassicalDensityGenerator`` (densidad de
tejido). En el futuro se puede añadir un ``AIDensityGenerator`` (p.ej. densidad
de células a partir de un modelo entrenado) que respete la misma interfaz y
sustituirlo mediante ``get_density_generator`` sin tocar los endpoints.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Any, List

import numpy as np
import matplotlib
from skimage.transform import resize

# Backend sin GUI para poder usar colormaps en un servidor.
matplotlib.use("Agg")

SUPPORTED_COLORMAPS = ("viridis", "hot", "magma", "plasma", "inferno", "jet")
DEFAULT_COLORMAP = "viridis"


@dataclass
class DensityMapResult:
    """Resultado de la generación de un mapa de densidades."""

    density: np.ndarray  # matriz float (rows, cols) en [0, 1]
    grid_size: int  # tamaño de celda en px de la imagen base
    rows: int
    cols: int
    colormap: str
    base_width: int
    base_height: int
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def density_min(self) -> float:
        return float(self.density.min()) if self.density.size else 0.0

    @property
    def density_max(self) -> float:
        return float(self.density.max()) if self.density.size else 0.0

    @property
    def density_mean(self) -> float:
        return float(self.density.mean()) if self.density.size else 0.0

    def stats(self) -> Dict[str, Any]:
        """Datos serializables (con la matriz) para guardar en BD."""
        return {
            "grid_size": self.grid_size,
            "rows": self.rows,
            "cols": self.cols,
            "colormap": self.colormap,
            "base_width": self.base_width,
            "base_height": self.base_height,
            "density_min": round(self.density_min, 6),
            "density_max": round(self.density_max, 6),
            "density_mean": round(self.density_mean, 6),
            "matrix": np.round(self.density, 6).tolist(),
            **self.extra,
        }


class DensityGenerator:
    """Interfaz de un generador de mapas de densidad."""

    def generate(  # pragma: no cover
        self,
        mask: np.ndarray,
        grid_size: int,
        base_width: int,
        base_height: int,
        colormap: str = DEFAULT_COLORMAP,
    ) -> DensityMapResult:
        raise NotImplementedError


class ClassicalDensityGenerator(DensityGenerator):
    """
    Generador clásico: densidad = fracción de tejido por celda.

    El grid se define en píxeles de la imagen base para que sea independiente
    de la resolución de la miniatura usada internamente.
    """

    MIN_GRID_SIZE = 8

    def generate(
        self,
        mask: np.ndarray,
        grid_size: int,
        base_width: int,
        base_height: int,
        colormap: str = DEFAULT_COLORMAP,
    ) -> DensityMapResult:
        if grid_size < self.MIN_GRID_SIZE:
            raise ValueError(
                f"grid_size debe ser >= {self.MIN_GRID_SIZE}px"
            )
        if colormap not in SUPPORTED_COLORMAPS:
            raise ValueError(f"colormap no soportado: {colormap}")

        mask = mask.astype(np.float64)
        thumb_h, thumb_w = mask.shape

        cols = max(1, math.ceil(base_width / grid_size))
        rows = max(1, math.ceil(base_height / grid_size))

        # Bordes de cada celda proyectados sobre la miniatura.
        col_edges = np.linspace(0, thumb_w, cols + 1).astype(int)
        row_edges = np.linspace(0, thumb_h, rows + 1).astype(int)

        density = np.zeros((rows, cols), dtype=np.float64)
        for r in range(rows):
            y0, y1 = row_edges[r], max(row_edges[r] + 1, row_edges[r + 1])
            for c in range(cols):
                x0, x1 = col_edges[c], max(col_edges[c] + 1, col_edges[c + 1])
                cell = mask[y0:y1, x0:x1]
                density[r, c] = float(cell.mean()) if cell.size else 0.0

        return DensityMapResult(
            density=density,
            grid_size=grid_size,
            rows=rows,
            cols=cols,
            colormap=colormap,
            base_width=base_width,
            base_height=base_height,
            extra={"method": "tissue_fraction_per_cell"},
        )


_default_generator = ClassicalDensityGenerator()


def get_density_generator() -> DensityGenerator:
    """
    Devuelve el generador de densidad activo.

    Punto único de sustitución: cuando exista un modelo de IA entrenado
    (p.ej. conteo de células), aquí se devolverá el generador correspondiente.
    """
    return _default_generator


def generate_density_map(
    mask: np.ndarray,
    grid_size: int,
    base_width: int,
    base_height: int,
    colormap: str = DEFAULT_COLORMAP,
) -> DensityMapResult:
    """Atajo que usa el generador activo."""
    return get_density_generator().generate(
        mask, grid_size, base_width, base_height, colormap
    )


def _colormap_lut(colormap: str, samples: int = 256) -> List[List[int]]:
    """Devuelve la tabla de colores (RGB 0-255) del colormap, para el colorbar."""
    cmap = matplotlib.colormaps[colormap]
    xs = np.linspace(0, 1, samples)
    rgba = cmap(xs)
    return (rgba[:, :3] * 255).astype(np.uint8).tolist()


def density_to_heatmap_rgba(
    density: np.ndarray,
    out_shape: tuple[int, int],
    colormap: str = DEFAULT_COLORMAP,
    alpha: int = 160,
) -> np.ndarray:
    """
    Convierte la matriz de densidades en un heatmap RGBA (H, W, 4) uint8
    escalado a ``out_shape`` (alto, ancho), coloreado con ``colormap``.

    Las celdas con densidad 0 quedan totalmente transparentes para no ensuciar
    el fondo; el resto usa la opacidad ``alpha``.
    """
    if colormap not in SUPPORTED_COLORMAPS:
        raise ValueError(f"colormap no soportado: {colormap}")

    cmap = matplotlib.colormaps[colormap]
    dmax = float(density.max()) if density.size else 0.0
    norm = density / dmax if dmax > 0 else np.zeros_like(density)

    rgba = cmap(norm)  # (rows, cols, 4) float en [0,1]
    rgb = (rgba[..., :3] * 255).astype(np.uint8)

    alpha_channel = np.where(density > 0, alpha, 0).astype(np.uint8)
    heat = np.dstack([rgb, alpha_channel])  # (rows, cols, 4)

    out_h, out_w = out_shape
    # Escalado por vecino más cercano para conservar los bloques del grid.
    resized = resize(
        heat,
        (out_h, out_w),
        order=0,
        preserve_range=True,
        anti_aliasing=False,
    ).astype(np.uint8)
    return resized
