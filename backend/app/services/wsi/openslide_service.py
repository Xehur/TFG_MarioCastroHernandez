import os
from openslide import OpenSlide, OpenSlideError
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

    def close(self) -> None:
        """Cierra la imagen."""
        if self.slide:
            self.slide.close()