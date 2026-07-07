import os
from openslide import OpenSlide, OpenSlideError
from openslide.deepzoom import DeepZoomGenerator
from PIL import Image as PILImage
from typing import Tuple, List, Optional


class OpenSlideService:
    SUPPORTED_FORMATS = {'.svs', '.tiff', '.tif', '.mrxs'}

    def __init__(self, file_path: str):
        """
        Inicializa el servicio con una ruta de archivo WSI.

        Args:
            file_path: Ruta al archivo WSI

        Raises:
            ValueError: Si el formato no es soportado
            OpenSlideError: Si no se puede abrir la imagen
        """
        self.file_path = file_path
        self._validate_format()
        self.slide = OpenSlide(file_path)

    def _validate_format(self) -> None:
        """Valida que el archivo tenga un formato soportado."""
        _, ext = os.path.splitext(self.file_path)
        if ext.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Formato no soportado: {ext}. Soportados: {self.SUPPORTED_FORMATS}")

    def get_dimensions(self) -> Tuple[int, int]:
        """
        Obtiene las dimensiones de la imagen (ancho, alto).

        Returns:
            Tupla (width, height)
        """
        return self.slide.dimensions

    def get_zoom_levels(self) -> List[int]:
        """
        Obtiene los niveles de zoom disponibles.

        Returns:
            Lista de niveles de zoom
        """
        return list(range(self.slide.level_count))

    def get_level_dimensions(self, level: int) -> Tuple[int, int]:
        """
        Obtiene las dimensiones para un nivel específico.

        Args:
            level: Nivel de zoom

        Returns:
            Tupla (width, height)
        """
        if level < 0 or level >= self.slide.level_count:
            raise ValueError(f"Nivel inválido: {level}. Disponibles: 0-{self.slide.level_count - 1}")
        return self.slide.level_dimensions[level]

    def get_downsamples(self) -> List[float]:
        """
        Obtiene los factores de reducción para cada nivel.

        Returns:
            Lista de downsamples
        """
        return list(self.slide.level_downsamples)

    def extract_tile(self, x: int, y: int, level: int, tile_size: int = 256) -> bytes:
        """
        Extrae un tile (región) de la imagen.

        Args:
            x: Coordenada X
            y: Coordenada Y
            level: Nivel de zoom
            tile_size: Tamaño del tile en píxeles

        Returns:
            Imagen PIL como bytes
        """
        if level < 0 or level >= self.slide.level_count:
            raise ValueError(f"Nivel inválido: {level}")

        region = self.slide.read_region((x, y), level, (tile_size, tile_size))
        return region

    def get_deepzoom_generator(
        self, tile_size: int = 256, overlap: int = 1, limit_bounds: bool = False
    ) -> DeepZoomGenerator:
        """
        Crea un generador Deep Zoom (DZI) para la imagen.

        DeepZoomGenerator construye la pirámide completa de niveles que
        espera OpenSeadragon y selecciona automáticamente el nivel de
        OpenSlide más adecuado para cada nivel DZI, escalando cuando es
        necesario. Esto evita los tiles en blanco entre niveles.

        Args:
            tile_size: Tamaño del tile en píxeles
            overlap: Solapamiento entre tiles (1 reduce las costuras visibles)
            limit_bounds: Si se recortan los bordes no-imagen

        Returns:
            Instancia de DeepZoomGenerator
        """
        return DeepZoomGenerator(
            self.slide,
            tile_size=tile_size,
            overlap=overlap,
            limit_bounds=limit_bounds,
        )

    def get_metadata(self) -> dict:
        """
        Obtiene metadatos de la imagen.

        Returns:
            Diccionario con metadatos
        """
        return {
            'dimensions': self.get_dimensions(),
            'level_count': self.slide.level_count,
            'zoom_levels': self.get_zoom_levels(),
            'downsamples': self.get_downsamples(),
            'properties': dict(self.slide.properties)
        }

    def get_thumbnail_rgb(self, max_size: int = 2048):
        """
        Obtiene una miniatura RGB de la imagen como array numpy (H, W, 3).

        Se usa para análisis a baja resolución (detección de tejido, mapas de
        densidad), evitando cargar la imagen completa en memoria.

        Args:
            max_size: lado máximo (px) de la miniatura.

        Returns:
            (array numpy uint8 RGB, escala) donde escala = tamaño_base / tamaño_thumb
        """
        import numpy as np

        width, height = self.slide.dimensions
        thumb = self.slide.get_thumbnail((max_size, max_size))
        if thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        arr = np.asarray(thumb, dtype=np.uint8)
        thumb_h = arr.shape[0]
        scale = height / thumb_h if thumb_h else 1.0
        return arr, scale

    def read_region_rgb(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        max_size: int = 2048,
    ):
        """
        Lee una región arbitraria de la imagen como array numpy RGB (H, W, 3).

        Selecciona automáticamente el nivel de la pirámide de forma que el lado
        mayor de la región no supere ``max_size`` píxeles, manteniendo bajo el
        uso de memoria. Se usa para analizar zonas concretas (anotaciones) a
        baja resolución (detección de tejido, mapas de densidad).

        Args:
            x, y: esquina superior izquierda de la región en píxeles de la
                imagen base (nivel 0).
            width, height: tamaño de la región en píxeles de la imagen base.
            max_size: lado máximo (px) de la región leída.

        Returns:
            (array numpy uint8 RGB, escala, bbox_usado) donde escala =
            tamaño_base / tamaño_leído y bbox_usado = (x, y, width, height) tras
            recortar a los límites de la imagen.
        """
        import numpy as np

        base_w, base_h = self.slide.dimensions

        # Normaliza anchos/altos negativos (formas dibujadas "hacia atrás").
        x = int(round(x))
        y = int(round(y))
        width = int(round(width))
        height = int(round(height))
        if width < 0:
            x += width
            width = -width
        if height < 0:
            y += height
            height = -height

        # Recorta a los límites de la imagen.
        x = max(0, min(x, base_w - 1))
        y = max(0, min(y, base_h - 1))
        width = max(1, min(width, base_w - x))
        height = max(1, min(height, base_h - y))

        # Elige el nivel cuyo downsample sea el mayor que aún deje la región
        # por encima de ``max_size`` (es decir, el más ligero suficiente).
        target_ds = max(1.0, max(width, height) / float(max_size))
        level = 0
        for i, ds in enumerate(self.slide.level_downsamples):
            if ds <= target_ds:
                level = i
            else:
                break
        ds = self.slide.level_downsamples[level]

        out_w = max(1, int(round(width / ds)))
        out_h = max(1, int(round(height / ds)))

        region = self.slide.read_region((x, y), level, (out_w, out_h))
        if region.mode != "RGB":
            region = region.convert("RGB")
        arr = np.asarray(region, dtype=np.uint8)

        scale = height / arr.shape[0] if arr.shape[0] else 1.0
        return arr, scale, (x, y, width, height)

    def get_mpp_x(self) -> Optional[float]:
        """Micras por píxel en X (magnificación física), o None si no consta."""
        try:
            value = float(self.slide.properties.get("openslide.mpp-x"))
        except (TypeError, ValueError):
            return None
        return value if value and value > 0 else None

    def read_patch_rgb(
        self,
        center_x: float,
        center_y: float,
        size_level0: int,
        out_size: int = 224,
    ):
        """
        Lee un parche cuadrado centrado en (center_x, center_y) para clasificación.

        El parche cubre ``size_level0`` px en coordenadas de nivel 0 y se
        devuelve como array RGB (out_size, out_size, 3). Se escoge el nivel de la
        pirámide más detallado cuyo downsample no supere el necesario para
        obtener ``out_size`` px, evitando leer (y descartar) resolución de más y
        preservando así la magnificación efectiva del parche.

        Args:
            center_x, center_y: centro del parche en píxeles de nivel 0.
            size_level0: lado del parche en píxeles de nivel 0.
            out_size: lado del parche devuelto (entrada del modelo).

        Returns:
            array numpy uint8 RGB (out_size, out_size, 3).
        """
        import numpy as np

        base_w, base_h = self.slide.dimensions
        size_level0 = max(1, int(round(size_level0)))

        x = int(round(center_x - size_level0 / 2.0))
        y = int(round(center_y - size_level0 / 2.0))
        x = max(0, min(x, max(0, base_w - size_level0)))
        y = max(0, min(y, max(0, base_h - size_level0)))

        # Nivel más detallado cuyo downsample siga sin sobre-reducir el parche.
        target_ds = max(1.0, size_level0 / float(out_size))
        level = 0
        for i, ds in enumerate(self.slide.level_downsamples):
            if ds <= target_ds + 1e-6:
                level = i
            else:
                break
        ds = self.slide.level_downsamples[level]
        read_size = max(1, int(round(size_level0 / ds)))

        region = self.slide.read_region((x, y), level, (read_size, read_size))
        if region.mode != "RGB":
            region = region.convert("RGB")
        if read_size != out_size:
            region = region.resize((out_size, out_size), PILImage.BICUBIC)
        return np.asarray(region, dtype=np.uint8)

    def close(self) -> None:
        """Cierra la imagen."""
        if self.slide:
            self.slide.close()