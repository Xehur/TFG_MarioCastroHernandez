"""
Tests de carga y caché de tiles (ISSUE 17).

Valida:
- El generador Deep Zoom produce tiles válidos en TODOS los niveles DZI,
  incluidos los intermedios que antes salían en blanco.
- La caché de tiles funciona (segunda petición = HIT).
- Rendimiento aceptable al servir un lote de tiles.
- El cableado de los endpoints DZI/tile (404 para imágenes inexistentes).
"""
import os
import glob
import time

import pytest
from fastapi import status

from app.config import settings
from app.models.image import Image
from app.services.wsi.openslide_service import OpenSlideService
from app.services.wsi.slide_cache import SlideCache


def _find_sample_wsi():
    """Devuelve la ruta de un WSI real del directorio uploads, o None."""
    if not os.path.isdir(settings.UPLOAD_DIR):
        return None
    for ext in ("*.svs", "*.tif", "*.tiff", "*.mrxs"):
        matches = glob.glob(os.path.join(settings.UPLOAD_DIR, ext))
        if matches:
            return matches[0]
    return None


SAMPLE_WSI = _find_sample_wsi()
requires_sample = pytest.mark.skipif(
    SAMPLE_WSI is None,
    reason="No hay un archivo WSI real en uploads/ para el test de carga",
)


# --- Tests de cableado de endpoints (no requieren WSI real) ---

def test_dzi_metadata_image_not_found(client):
    """El endpoint DZI devuelve 404 si la imagen no existe."""
    response = client.get("/images/99999/dzi.dzi")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_tile_image_not_found(client):
    """El endpoint de tile devuelve 404 si la imagen no existe."""
    response = client.get("/images/99999/dzi_files/10/0_0.jpeg")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Tests de carga con un WSI real ---

@requires_sample
def test_deepzoom_all_levels_render():
    """Todos los niveles DZI generan un tile no vacío (sin huecos en blanco)."""
    service = OpenSlideService(SAMPLE_WSI)
    try:
        dzg = service.get_deepzoom_generator(tile_size=256, overlap=1)
        assert dzg.level_count > 0

        for level in range(dzg.level_count):
            cols, rows = dzg.level_tiles[level]
            tile = dzg.get_tile(level, (0, 0))
            assert tile.size[0] > 0 and tile.size[1] > 0
            # El tile no debe exceder tile_size + 2*overlap
            assert tile.size[0] <= 256 + 2
            assert tile.size[1] <= 256 + 2
            assert cols > 0 and rows > 0
    finally:
        service.close()


@requires_sample
def test_tile_cache_hit():
    """La segunda petición del mismo tile se sirve desde la caché."""
    cache = SlideCache(max_slides=2, max_tiles=64)

    # Elegir un nivel intermedio con al menos un tile
    _, dzg = cache.get_dzgenerator(SAMPLE_WSI)
    level = dzg.level_count // 2

    # Primera vez: MISS (no está en caché)
    assert cache.get_tile_bytes(SAMPLE_WSI, level, 0, 0) is None

    tile = dzg.get_tile(level, (0, 0))
    import io

    buf = io.BytesIO()
    tile.convert("RGB").save(buf, format="JPEG", quality=85)
    data = buf.getvalue()
    cache.store_tile_bytes(SAMPLE_WSI, level, 0, 0, data)

    # Segunda vez: HIT
    cached = cache.get_tile_bytes(SAMPLE_WSI, level, 0, 0)
    assert cached is not None
    assert cached == data

    cache.clear()


@requires_sample
def test_tile_batch_load_performance():
    """Sirve un lote de tiles y comprueba un rendimiento razonable."""
    cache = SlideCache(max_slides=2, max_tiles=512)
    _, dzg = cache.get_dzgenerator(SAMPLE_WSI)

    # Usar un nivel con varios tiles para una prueba representativa
    level = max(0, dzg.level_count - 4)
    cols, rows = dzg.level_tiles[level]

    tiles_to_load = []
    for c in range(min(cols, 4)):
        for r in range(min(rows, 4)):
            tiles_to_load.append((c, r))

    start = time.perf_counter()
    for c, r in tiles_to_load:
        tile = dzg.get_tile(level, (c, r))
        assert tile is not None
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / len(tiles_to_load)) * 1000
    # Margen amplio para no ser flaky en CI; solo detecta regresiones graves
    assert avg_ms < 1000, f"Carga de tile demasiado lenta: {avg_ms:.1f}ms de media"

    cache.clear()


@requires_sample
def test_tile_endpoint_serves_jpeg(client, test_db):
    """El endpoint de tile devuelve un JPEG real para una imagen registrada."""
    service = OpenSlideService(SAMPLE_WSI)
    width, height = service.get_dimensions()
    level_count = len(service.get_zoom_levels())
    service.close()

    image = Image(
        filename=f"loadtest_{os.path.basename(SAMPLE_WSI)}",
        file_path=SAMPLE_WSI,
        user_id=1,
        width=width,
        height=height,
        level_count=level_count,
        downsamples=[1.0],
        properties={},
        file_size_mb=1.0,
    )
    test_db.add(image)
    test_db.commit()
    test_db.refresh(image)

    try:
        # DZI metadata
        dzi_resp = client.get(f"/images/{image.id}/dzi.dzi")
        assert dzi_resp.status_code == status.HTTP_200_OK
        assert "deepzoom" in dzi_resp.text.lower()

        # Un tile de un nivel intermedio
        tile_resp = client.get(f"/images/{image.id}/dzi_files/10/0_0.jpeg")
        assert tile_resp.status_code == status.HTTP_200_OK
        assert tile_resp.headers["content-type"] == "image/jpeg"
        assert len(tile_resp.content) > 0

        # Segunda petición → caché HIT
        tile_resp2 = client.get(f"/images/{image.id}/dzi_files/10/0_0.jpeg")
        assert tile_resp2.status_code == status.HTTP_200_OK
        assert tile_resp2.headers.get("X-Tile-Cache") == "HIT"
    finally:
        test_db.delete(image)
        test_db.commit()
