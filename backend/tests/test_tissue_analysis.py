"""
Tests del algoritmo de detección de tejido y de los endpoints de análisis.
"""
import os
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.image import Image
from app.services.analysis import tissue_detection, tissue_service


# --- Utilidades --------------------------------------------------------------

def _synthetic_slide_rgb(size=120, block=40):
    """Fondo blanco con un bloque central coloreado (tejido simulado)."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    start = (size - block) // 2
    img[start:start + block, start:start + block] = [150, 40, 80]
    return img


class _FakeSlide:
    """Sustituto de OpenSlideService que devuelve una miniatura sintética."""

    def __init__(self, file_path):
        self.file_path = file_path

    def get_thumbnail_rgb(self, max_size=2048):
        return _synthetic_slide_rgb(), 1.0

    def close(self):
        pass


def _make_image_with_file(filename="tissue_test.svs", user_id=1):
    """Crea un registro Image y un archivo dummy en disco."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(file_path, "wb") as fh:
        fh.write(b"dummy")

    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        image = Image(
            filename=filename,
            file_path=file_path,
            user_id=user_id,
            width=120,
            height=120,
            level_count=1,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image.id, file_path
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _patch_slide(monkeypatch):
    """Evita depender de un archivo WSI real en los tests de endpoint."""
    monkeypatch.setattr(tissue_service, "OpenSlideService", _FakeSlide)
    yield


# --- Tests del algoritmo -----------------------------------------------------

def test_tissue_mask_stats_include_detector_mode(client):
    image_id, _ = _make_image_with_file(filename="tissue_mode1.svs")
    data = client.get(f"/images/{image_id}/tissue-mask/stats").json()
    assert data["result_data"]["detector_mode"] == "classical"


def test_get_or_create_regenerates_when_old_ai_mask_cached(monkeypatch, tmp_path):
    """Las máscaras del antiguo detector de IA (detector_mode != classical) se regeneran."""
    fake_png = tmp_path / "m.png"
    fake_png.write_bytes(b"x")

    class _Cached:
        result_data = {"mask_path": str(fake_png), "detector_mode": "ai"}

    monkeypatch.setattr(tissue_service, "get_cached_result", lambda db, iid: _Cached())
    called = {"n": 0}

    def _fake_gen(*args, **kwargs):
        called["n"] += 1
        return "GENERATED"

    monkeypatch.setattr(tissue_service, "generate_tissue_mask", _fake_gen)
    out = tissue_service.get_or_create_tissue_mask(None, 1, "path.svs")
    assert out == "GENERATED"
    assert called["n"] == 1


def test_get_or_create_uses_cache_for_classical_mask(monkeypatch, tmp_path):
    fake_png = tmp_path / "m.png"
    fake_png.write_bytes(b"x")

    class _Cached:
        result_data = {
            "mask_path": str(fake_png),
            "detector_mode": "classical",
            "detector_version": tissue_detection.DETECTOR_VERSION,
        }

    cached = _Cached()
    monkeypatch.setattr(tissue_service, "get_cached_result", lambda db, iid: cached)

    def _fail(*args, **kwargs):
        raise AssertionError("no debería regenerar con la caché válida")

    monkeypatch.setattr(tissue_service, "generate_tissue_mask", _fail)
    out = tissue_service.get_or_create_tissue_mask(None, 1, "path.svs")
    assert out is cached


def test_detect_tissue_basic():
    result = tissue_detection.detect_tissue(_synthetic_slide_rgb())
    assert result.width == 120 and result.height == 120
    assert 5 < result.tissue_percent < 30
    assert result.mask.dtype == bool
    assert result.mask.sum() > 0


def test_detect_tissue_all_background():
    """Imagen blanca uniforme: no debería detectar tejido."""
    white = np.full((80, 80, 3), 255, dtype=np.uint8)
    result = tissue_detection.detect_tissue(white)
    assert result.tissue_percent == 0.0
    assert result.mask.sum() == 0


def test_detect_tissue_handles_grayscale_input():
    gray = np.full((60, 60), 200, dtype=np.uint8)
    gray[20:40, 20:40] = 30
    result = tissue_detection.detect_tissue(gray)
    assert result.mask.sum() > 0


def test_detect_tissue_handles_rgba_input():
    rgba = np.full((60, 60, 4), 240, dtype=np.uint8)
    rgba[..., 3] = 255
    rgba[20:40, 20:40, :3] = [140, 30, 70]
    result = tissue_detection.detect_tissue(rgba)
    assert result.mask.shape == (60, 60)
    assert result.mask.sum() > 0


def test_stats_serializable():
    result = tissue_detection.detect_tissue(_synthetic_slide_rgb())
    stats = result.stats()
    assert "tissue_percent" in stats
    assert stats["width"] == 120
    assert stats["method"] == "od_hysteresis"
    assert stats["detector_version"] == tissue_detection.DETECTOR_VERSION


def test_mask_to_rgba_overlay():
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 2:5] = True
    overlay = tissue_detection.mask_to_rgba_overlay(mask, color=(1, 2, 3), alpha=200)
    assert overlay.shape == (10, 10, 4)
    assert list(overlay[3, 3]) == [1, 2, 3, 200]
    assert list(overlay[0, 0]) == [0, 0, 0, 0]


# --- Tests del detector de tejido --------------------------------------------

def test_get_tissue_detector_is_classical():
    detector = tissue_detection.get_tissue_detector()
    assert isinstance(detector, tissue_detection.ClassicalTissueDetector)


# --- Tests de endpoints ------------------------------------------------------

def test_get_tissue_mask_returns_png(client):
    image_id, _ = _make_image_with_file()
    resp = client.get(f"/images/{image_id}/tissue-mask")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_tissue_mask_stats(client):
    image_id, _ = _make_image_with_file(filename="tissue_test2.svs")
    resp = client.get(f"/images/{image_id}/tissue-mask/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_type"] == "tissue_mask"
    assert "tissue_percent" in data["result_data"]
    assert data["image_id"] == image_id


def test_tissue_mask_is_cached(client):
    image_id, _ = _make_image_with_file(filename="tissue_test3.svs")
    first = client.get(f"/images/{image_id}/tissue-mask/stats").json()
    second = client.get(f"/images/{image_id}/tissue-mask/stats").json()
    # Mismo registro (no se crea uno nuevo)
    assert first["id"] == second["id"]


def test_analyze_tissue_forces_regeneration(client):
    image_id, _ = _make_image_with_file(filename="tissue_test4.svs")
    first = client.get(f"/images/{image_id}/tissue-mask/stats").json()
    resp = client.post(f"/images/{image_id}/analyze/tissue")
    assert resp.status_code == 201
    # El id del registro se mantiene (se actualiza in-place)
    assert resp.json()["id"] == first["id"]


def test_tissue_mask_image_not_found(client):
    resp = client.get("/images/99999/tissue-mask")
    assert resp.status_code == 404


def test_tissue_mask_requires_auth(anon_client):
    image_id, _ = _make_image_with_file(filename="tissue_test5.svs")
    resp = anon_client.get(f"/images/{image_id}/tissue-mask")
    assert resp.status_code in (401, 403)


# --- Detector OD + histéresis: tejido pálido y artefactos --------------------

def _slide_with_pale_tissue():
    """Cristal (244) con tejido teñido intenso y una zona pálida contigua."""
    img = np.full((200, 300, 3), 244, dtype=np.uint8)
    img[60:140, 40:140] = [150, 60, 130]   # tejido bien teñido
    img[60:140, 140:240] = [232, 214, 226]  # tejido pálido (grasa/estroma laxo)
    return img


def test_detecta_tejido_palido_conectado():
    rgb = _slide_with_pale_tissue()
    mask = tissue_detection.detect_tissue(rgb).mask
    assert mask[100, 90]   # tejido intenso
    assert mask[100, 190]  # tejido pálido: antes quedaba fuera
    assert not mask[20, 20]  # cristal


def test_mancha_palida_aislada_no_es_tejido():
    rgb = _slide_with_pale_tissue()
    rgb[160:190, 250:290] = [234, 234, 234]  # mancha gris sin conexión con tejido
    mask = tissue_detection.detect_tissue(rgb).mask
    assert not mask[175, 270]


def test_tinta_de_rotulador_se_excluye():
    rgb = _slide_with_pale_tissue()
    rgb[10:40, 160:290] = [60, 160, 130]    # trazo verde
    rgb[18:32, 175:275] = [190, 225, 215]   # interior pálido del trazo
    result = tissue_detection.detect_tissue(rgb)
    assert not result.mask[25, 220]
    assert not result.mask[15, 220]
    assert result.mask[100, 90]
    assert result.extra["pen_ink_percent"] > 0


def test_franja_del_borde_del_escaner_se_elimina():
    rgb = _slide_with_pale_tissue()
    rgb[0:6, :] = [175, 175, 170]           # sombra del escáner en el borde
    rgb[0:60, 80:110] = [150, 60, 130]      # el tejido llega hasta la franja
    mask = tissue_detection.detect_tissue(rgb).mask
    assert not mask[2, 250]  # franja fuera
    assert mask[2, 95]       # la punta del tejido que entra en la franja se mantiene
    assert mask[100, 90]


def test_region_toda_tejido_no_se_recorta():
    """Una anotación completamente dentro del tejido no pierde sus bordes."""
    rgb = np.full((100, 100, 3), [150, 60, 130], dtype=np.uint8)
    rgb[40:60, 40:60] = [235, 225, 232]
    mask = tissue_detection.detect_tissue(rgb).mask
    assert mask[0, :].all() and mask[:, 0].all()


def test_cache_de_detector_antiguo_se_regenera(monkeypatch, tmp_path):
    fake_png = tmp_path / "m.png"
    fake_png.write_bytes(b"x")

    class _Cached:
        result_data = {"mask_path": str(fake_png), "detector_mode": "classical"}

    monkeypatch.setattr(tissue_service, "get_cached_result", lambda db, iid: _Cached())
    monkeypatch.setattr(tissue_service, "generate_tissue_mask", lambda *a, **k: "GENERATED")
    assert tissue_service.get_or_create_tissue_mask(None, 1, "path.svs") == "GENERATED"


def test_tejido_que_absorbe_en_un_solo_canal():
    """Rosa muy pálido (solo absorbe en el verde, poca saturación): lo detecta la
    OD MÁXIMA entre canales. Con la OD mínima quedaría fuera."""
    img = np.full((200, 300, 3), 244, dtype=np.uint8)
    img[60:140, 40:140] = [150, 60, 130]
    img[60:140, 140:240] = [242, 224, 240]  # saturación ≈ 0.074 < 0.08
    mask = tissue_detection.detect_tissue(img).mask
    assert mask[100, 200]


# --- Factor de umbral ajustable por el usuario ---------------------------------

def test_factor_de_umbral_mas_alto_detecta_menos_tejido():
    rgb = _slide_with_pale_tissue()
    auto = tissue_detection.detect_tissue(rgb)
    strict = tissue_detection.detect_tissue(rgb, threshold_factor=3.0)
    assert auto.extra["threshold_factor"] == 1.0
    assert strict.extra["threshold_factor"] == 3.0
    # Con un umbral más exigente el tejido pálido deja de considerarse tejido,
    # pero el bien teñido se mantiene.
    assert auto.mask[100, 190] and not strict.mask[100, 190]
    assert strict.mask[100, 90]
    assert strict.tissue_percent < auto.tissue_percent


def test_factor_de_umbral_se_limita_al_rango():
    assert tissue_detection.clamp_threshold_factor(None) == 1.0
    assert tissue_detection.clamp_threshold_factor(0.01) == tissue_detection.MIN_THRESHOLD_FACTOR
    assert tissue_detection.clamp_threshold_factor(99) == tissue_detection.MAX_THRESHOLD_FACTOR


def test_cache_distingue_el_factor_de_umbral():
    data = {"detector_version": tissue_detection.DETECTOR_VERSION}
    assert tissue_detection.is_current_detector(data)  # sin factor = 1.0
    assert not tissue_detection.is_current_detector(data, 1.5)
    data["threshold_factor"] = 1.5
    assert tissue_detection.is_current_detector(data, 1.5)


def test_vista_previa_no_guarda_y_devuelve_porcentaje(client):
    image_id, _ = _make_image_with_file(filename="tissue_preview.svs")
    resp = client.get(f"/images/{image_id}/tissue-mask/preview?threshold_factor=1.5")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert float(resp.headers["x-tissue-percent"]) > 0
    assert resp.headers["x-threshold-factor"] == "1.500"
    # No se ha persistido: la máscara guardada sigue con el factor automático.
    stats = client.get(f"/images/{image_id}/tissue-mask/stats").json()["result_data"]
    assert stats["threshold_factor"] == 1.0


def test_vista_previa_rechaza_factor_fuera_de_rango(client):
    image_id, _ = _make_image_with_file(filename="tissue_preview_bad.svs")
    assert client.get(
        f"/images/{image_id}/tissue-mask/preview?threshold_factor=10"
    ).status_code == 422


def test_aplicar_factor_lo_guarda_para_la_imagen(client):
    image_id, _ = _make_image_with_file(filename="tissue_apply.svs")
    resp = client.post(f"/images/{image_id}/analyze/tissue?threshold_factor=2")
    assert resp.status_code == 201
    assert resp.json()["result_data"]["threshold_factor"] == 2.0
    # Se conserva al pedir de nuevo la máscara y al re-analizar sin factor.
    stats = client.get(f"/images/{image_id}/tissue-mask/stats").json()["result_data"]
    assert stats["threshold_factor"] == 2.0
    again = client.post(f"/images/{image_id}/analyze/tissue").json()["result_data"]
    assert again["threshold_factor"] == 2.0
