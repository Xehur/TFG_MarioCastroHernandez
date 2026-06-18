"""
Caché de slides WSI y de tiles ya generados.

Evita reabrir el archivo WSI y reconstruir el DeepZoomGenerator en cada
petición de tile (muy costoso) y guarda en memoria los últimos tiles
servidos para acelerar la navegación y el re-zoom.
"""
import threading
import logging
from collections import OrderedDict
from typing import Tuple

from app.services.wsi.openslide_service import OpenSlideService

logger = logging.getLogger(__name__)


class _LRUCache:
    """Caché LRU genérica y thread-safe."""

    def __init__(self, max_size: int):
        self.max_size = max_size
        self._data: "OrderedDict" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        return None

    def set(self, key, value, on_evict=None):
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_size:
                _, evicted = self._data.popitem(last=False)
                if on_evict:
                    on_evict(evicted)

    def clear(self, on_evict=None):
        with self._lock:
            if on_evict:
                for value in self._data.values():
                    on_evict(value)
            self._data.clear()


class SlideCache:
    """
    Gestiona el ciclo de vida de los OpenSlideService + DeepZoomGenerator
    y una caché LRU de tiles JPEG ya renderizados.
    """

    def __init__(
        self,
        max_slides: int = 8,
        max_tiles: int = 2048,
        tile_size: int = 256,
        overlap: int = 1,
    ):
        self.tile_size = tile_size
        self.overlap = overlap
        self._slides = _LRUCache(max_slides)
        self._tiles = _LRUCache(max_tiles)
        self._open_lock = threading.Lock()

    @staticmethod
    def _close_slide(entry):
        service, _ = entry
        try:
            service.close()
        except Exception:  # noqa: BLE001
            pass

    def get_dzgenerator(self, file_path: str):
        """Devuelve (service, dz_generator) cacheado, creándolo si hace falta."""
        entry = self._slides.get(file_path)
        if entry is not None:
            return entry

        # Solo un hilo abre el slide a la vez para no duplicar trabajo costoso
        with self._open_lock:
            entry = self._slides.get(file_path)
            if entry is not None:
                return entry

            service = OpenSlideService(file_path)
            dzg = service.get_deepzoom_generator(
                tile_size=self.tile_size, overlap=self.overlap
            )
            entry = (service, dzg)
            self._slides.set(file_path, entry, on_evict=self._close_slide)
            logger.info("Slide abierto y cacheado: %s", file_path)
            return entry

    def get_tile_bytes(self, file_path: str, level: int, col: int, row: int) -> bytes:
        """Devuelve los bytes JPEG del tile, usando la caché cuando es posible."""
        cache_key = (file_path, level, col, row)
        cached = self._tiles.get(cache_key)
        if cached is not None:
            return cached
        return None

    def store_tile_bytes(self, file_path: str, level: int, col: int, row: int, data: bytes):
        cache_key = (file_path, level, col, row)
        self._tiles.set(cache_key, data)

    def clear(self):
        self._slides.clear(on_evict=self._close_slide)
        self._tiles.clear()


# Instancia global compartida por la aplicación
slide_cache = SlideCache()
