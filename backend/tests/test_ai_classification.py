"""
Tests de la clasificación de tejido por IA (InceptionV3, tejido mamario BACH).

Cubren las funciones puras (rejilla, leyenda, resumen, escala), la clasificación
con un clasificador simulado (para no ejecutar el modelo real en cada test), la
invalidación de caché por modelo, el error 503 sin pesos y los endpoints
``/images|annotations/{id}/ai-classification``. Si el checkpoint real está
disponible, se comprueba además que carga y produce salidas (N, 4).
"""
import os

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.analysis import AnalysisResult
from app.models.image import Image
from app.services.analysis import ai_classification_service as ai
from app.services.analysis import annotation_analysis_service
from app.services.analysis import inception_classifier as ic


# --- Utilidades --------------------------------------------------------------

def _tissue_region(h=120, w=160, margin=16):
    """Región RGB con borde claro e interior de 'tejido' (saturado y oscuro).

    La variación claro/oscuro es necesaria para que la detección de tejido por
    Otsu pueda segmentar (una imagen uniforme no tiene umbral).
    """
    img = np.full((h, w, 3), (235, 235, 235), dtype=np.uint8)
    img[margin:h - margin, margin:w - margin] = (150, 40, 80)
    return img


class _FakeSlide:
    """Sustituto de OpenSlideService que devuelve una región de tejido."""

    field_calls = []

    def __init__(self, file_path):
        self.file_path = file_path

    def get_thumbnail_rgb(self, max_size=2048):
        return _tissue_region(), 1.0

    def read_region_rgb(self, x, y, width, height, max_size=2048):
        return _tissue_region(), 1.0, (int(x), int(y), 160, 120)

    def get_mpp_x(self):
        return 0.5

    centers = []

    def read_field_rgb(self, cx, cy, w0, h0, out_w, out_h):
        _FakeSlide.field_calls.append((w0, h0, out_w, out_h))
        _FakeSlide.centers.append((cx, cy))
        return np.full((out_h, out_w, 3), (150, 40, 80), dtype=np.uint8)

    def close(self):
        pass


class _FakeClassifier:
    """Clasificador simulado: predice siempre la clase de índice ``idx``."""

    def __init__(self, idx=2):  # 2 = INVASIVE
        self.idx = idx
        self.seen_shapes = []

    def predict_batch(self, images, batch_size=16):
        self.seen_shapes += [np.asarray(i).shape for i in images]
        probs = np.full((len(images), 4), 0.02, dtype=np.float32)
        probs[:, self.idx] = 0.94
        return probs

    def info(self):
        return {
            "id": ic.MODEL_ID,
            "arch": ic.MODEL_ARCH,
            "dataset": ic.MODEL_DATASET,
            "classes": list(ic.MODEL_CLASSES),
            "preprocessing_version": ic.PREPROCESSING_VERSION,
            "weights_sha256": "fake",
            "device": "cpu",
        }


@pytest.fixture(autouse=True)
def _patch_ai(monkeypatch):
    _FakeSlide.field_calls = []
    _FakeSlide.centers = []
    monkeypatch.setattr(ai, "OpenSlideService", _FakeSlide)
    monkeypatch.setattr(annotation_analysis_service, "OpenSlideService", _FakeSlide)
    monkeypatch.setattr(ai, "get_classifier", lambda: _FakeClassifier())
    yield


def _session():
    engine = create_engine(
        "sqlite:///./test.db", connect_args={"check_same_thread": False}
    )
    return sessionmaker(bind=engine)()


def _make_image_with_file(filename="ai_test.svs", user_id=1):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(file_path, "wb") as fh:
        fh.write(b"dummy")

    db = _session()
    try:
        image = Image(
            filename=filename,
            file_path=file_path,
            user_id=user_id,
            width=1000,
            height=800,
            level_count=1,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image.id, file_path
    finally:
        db.close()


def _create_annotation(client, image_id, payload):
    resp = client.post(f"/images/{image_id}/annotations", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


_RECT = {
    "shape_type": "rectangle",
    "coordinates": {"x": 100, "y": 100, "width": 200, "height": 150},
    "color": "#FF0000",
}


# --- Funciones puras ---------------------------------------------------------

def test_grid_shape_proporcional():
    cols, rows = ai._grid_shape(1000, 500, 200)
    assert cols >= rows
    assert cols * rows <= 260


def test_class_codes_siguen_orden_del_modelo():
    assert [c.lower() for c in ai.CLASS_CODES] == ic.MODEL_CLASSES
    assert ic.MODEL_CLASSES == ["benign", "insitu", "invasive", "normal"]


def test_class_legend():
    legend = ai.class_legend()
    assert [c["code"] for c in legend] == ["BENIGN", "INSITU", "INVASIVE", "NORMAL"]
    # El fondo no es una clase del modelo.
    assert "BACK" not in {c["code"] for c in legend}


def test_build_summary_percentages():
    counts = {c: 0 for c in ai.CLASS_CODES}
    counts["INVASIVE"] = 6
    counts["NORMAL"] = 2
    summary = ai._build_summary(counts)
    assert summary["dominant_class"] == "INVASIVE"
    assert summary["dominant_group"] == "Carcinoma invasivo"
    assert len(summary["classes"]) == 4
    assert [g["group"] for g in summary["groups"]] == ai.GROUP_ORDER
    total = sum(g["percent"] for g in summary["groups"])
    assert abs(total - 100.0) < 0.1
    inv = next(c for c in summary["classes"] if c["code"] == "INVASIVE")
    assert inv["percent"] == 75.0


def test_build_summary_sin_tejido():
    summary = ai._build_summary({c: 0 for c in ai.CLASS_CODES})
    assert summary["dominant_class"] is None
    assert summary["dominant_group"] is None
    assert summary["tissue_patches"] == 0


def test_field_size_escala_con_mpp():
    # A 0.42 MPP el campo es exactamente el de BACH; a 0.21 MPP, el doble de px.
    assert ai.field_size_level0(0.42) == (2048, 1536)
    assert ai.field_size_level0(0.21) == (4096, 3072)


def test_classify_rgb_con_clasificador_simulado():
    rgb = _tissue_region()
    mask = np.ones(rgb.shape[:2], dtype=bool)
    result = ai.classify_rgb(rgb, mask, max_patches=64)
    assert result["overlay"].shape == (rgb.shape[0], rgb.shape[1], 4)
    assert result["tissue_patches"] > 0
    assert result["counts"]["INVASIVE"] == result["tissue_patches"]
    painted = result["overlay"][..., 3] > 0
    assert painted.any()
    r, g, b = ai.GROUP_COLORS["Carcinoma invasivo"]
    assert (result["overlay"][painted, 0] == r).all()
    assert (result["overlay"][painted, 1] == g).all()
    assert (result["overlay"][painted, 2] == b).all()


def test_overlay_color_normal(monkeypatch):
    monkeypatch.setattr(ai, "get_classifier", lambda: _FakeClassifier(idx=3))
    rgb = _tissue_region()
    result = ai.classify_rgb(rgb, np.ones(rgb.shape[:2], dtype=bool), max_patches=64)
    painted = result["overlay"][..., 3] > 0
    green = ai.GROUP_COLORS["Normal"]
    assert painted.any()
    assert (result["overlay"][painted, :3] == green).all()


def test_classify_rgb_sin_tejido_no_invoca_modelo(monkeypatch):
    def _boom():
        raise AssertionError("no debería cargarse el modelo")

    monkeypatch.setattr(ai, "get_classifier", _boom)
    rgb = _tissue_region()
    result = ai.classify_rgb(rgb, np.zeros(rgb.shape[:2], dtype=bool), max_patches=16)
    assert result["tissue_patches"] == 0
    assert not (result["overlay"][..., 3] > 0).any()


def test_classify_slide_region_lee_campo_bach():
    rgb = _tissue_region()
    mask = np.ones(rgb.shape[:2], dtype=bool)
    # Región de 20000x15000 px a 0.5 MPP.
    result = ai.classify_slide_region(
        _FakeSlide("x"), (0, 0, 20000, 15000), rgb, mask, max_patches=500
    )
    w0, h0, out_w, out_h = _FakeSlide.field_calls[0]
    # 2048 px * 0.42/0.5 = 1720 ; 1536 * 0.84 = 1290
    assert (w0, h0) == (1720, 1290)
    assert out_h == ic.MODEL_INPUT_SIZE and out_w == 399  # aspecto 4:3
    assert result["field_um"] == [860.0, 645.0]
    assert result["mpp_source"] == "metadata"
    assert result["tissue_patches"] > 0
    assert not result["field_exceeds_region"]


def _big_region_with_tissue_corner():
    """Miniatura 300x400 con tejido solo en su cuarto superior izquierdo."""
    rgb = np.full((300, 400, 3), 235, dtype=np.uint8)
    mask = np.zeros((300, 400), dtype=bool)
    mask[:150, :200] = True
    # Región 200000x150000 px a 0.5 MPP -> rejilla densa 117x117 campos.
    return rgb, mask, (0, 0, 200000, 150000)


def test_presupuesto_solo_se_gasta_en_tejido():
    rgb, mask, bbox = _big_region_with_tissue_corner()
    result = ai.classify_slide_region(_FakeSlide("x"), bbox, rgb, mask, max_patches=5000)
    assert result["cols"] == 117 and result["rows"] == 117
    # Solo se leen las celdas con tejido (≈ 1/4 de la rejilla), todas ellas.
    assert len(_FakeSlide.field_calls) == result["tissue_cells"]
    assert result["tissue_cells"] < result["total_patches"] / 3
    assert result["coverage"] == 1.0
    assert result["sampled"] is False
    assert result["inferred_cells"] == 0


def test_muestreo_repartido_y_relleno_atenuado():
    rgb, mask, bbox = _big_region_with_tissue_corner()
    result = ai.classify_slide_region(_FakeSlide("x"), bbox, rgb, mask, max_patches=200)
    assert len(_FakeSlide.field_calls) <= 200
    assert result["tissue_patches"] == len(_FakeSlide.field_calls)
    assert result["sampled"] is True
    assert result["inferred_cells"] == result["tissue_cells"] - result["tissue_patches"]
    # Los recuentos solo incluyen campos evaluados por el modelo.
    assert sum(result["counts"].values()) == result["tissue_patches"]
    alphas = set(np.unique(result["overlay"][..., 3]).tolist())
    assert {0, 80, 140}.issubset(alphas)  # fondo, inferidas, evaluadas
    # El fondo (fuera del cuarto con tejido) queda transparente.
    assert (result["overlay"][200:, 300:, 3] == 0).all()


def test_spread_sample_reparte_uniformemente():
    idx = ai._spread_sample(1000, 10)
    assert len(idx) == 10 and idx[0] == 0 and idx[-1] == 999
    assert list(ai._spread_sample(5, 10)) == [0, 1, 2, 3, 4]


# --- Clasificador InceptionV3 ------------------------------------------------

def test_to_rgb_uint8_normaliza_formatos():
    gray = np.zeros((10, 12), dtype=np.uint8)
    rgba = np.zeros((10, 12, 4), dtype=np.uint8)
    assert ic.to_rgb_uint8(gray).shape == (10, 12, 3)
    assert ic.to_rgb_uint8(rgba).shape == (10, 12, 3)
    with pytest.raises(ValueError):
        ic.to_rgb_uint8(np.zeros((10, 12, 2), dtype=np.uint8))


def test_checkpoint_ausente_lanza_error_claro(tmp_path):
    clf = ic.InceptionClassifier(str(tmp_path / "no_existe.pth"))
    with pytest.raises(ic.ModelUnavailableError):
        clf.load()


@pytest.mark.skipif(
    not os.path.isfile(settings.INCEPTION_WEIGHTS_PATH),
    reason="Checkpoint InceptionV3 no disponible",
)
def test_checkpoint_real_produce_4_clases():
    clf = ic.InceptionClassifier(settings.INCEPTION_WEIGHTS_PATH).load()
    assert clf._model.transform_input is True  # como en el entrenamiento
    imgs = [
        np.full((1536, 2048, 3), (200, 120, 180), dtype=np.uint8),
        np.full((50, 60), 128, dtype=np.uint8),  # gris, otro tamaño
    ]
    probs = clf.predict_batch(imgs)
    assert probs.shape == (2, 4)
    assert np.isfinite(probs).all()
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-4)
    assert clf.info()["weights_sha256"] == settings.INCEPTION_WEIGHTS_SHA256


# --- Endpoints: imagen -------------------------------------------------------

def test_image_ai_stats(client):
    image_id, _ = _make_image_with_file("ai_img1.svs")
    resp = client.get(f"/images/{image_id}/ai-classification/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_type"] == "ai_classification"
    rd = data["result_data"]
    assert rd["dominant_class"] == "INVASIVE"
    assert rd["dominant_group"] == "Carcinoma invasivo"
    assert len(rd["classes"]) == 4
    assert rd["model"]["id"] == ic.MODEL_ID
    assert rd["model"]["arch"] == "inception_v3"
    assert rd["sampling"]["field_um"] == [860.0, 645.0]
    assert rd["disclaimer"]
    assert set(rd["mean_probabilities"]) == set(ai.CLASS_CODES)


def test_image_ai_png(client):
    image_id, _ = _make_image_with_file("ai_img2.svs")
    resp = client.get(f"/images/{image_id}/ai-classification")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_ai_analyze_post(client):
    image_id, _ = _make_image_with_file("ai_img3.svs")
    resp = client.post(f"/images/{image_id}/analyze/ai")
    assert resp.status_code == 201
    assert resp.json()["result_data"]["dominant_class"] == "INVASIVE"


def test_image_ai_cached(client):
    image_id, _ = _make_image_with_file("ai_img4.svs")
    first = client.get(f"/images/{image_id}/ai-classification/stats").json()
    second = client.get(f"/images/{image_id}/ai-classification/stats").json()
    assert first["id"] == second["id"]
    assert first["created_at"] == second["created_at"]


def test_cache_de_modelo_antiguo_se_regenera(client):
    """Un resultado del modelo anterior (ResNet18) no se sirve como si fuera nuevo."""
    image_id, _ = _make_image_with_file("ai_img_old.svs")
    png = os.path.join(ai._image_dir(image_id), "ai_classification.png")
    with open(png, "wb") as fh:
        fh.write(b"old")
    db = _session()
    try:
        db.add(
            AnalysisResult(
                image_id=image_id,
                analysis_type=ai.AI_ANALYSIS_TYPE,
                result_data={
                    "model": {"id": "1aurent/resnet18.tiatoolbox-kather100k"},
                    "map_path": png,
                    "dominant_class": "TUM",
                },
            )
        )
        db.commit()
    finally:
        db.close()

    rd = client.get(f"/images/{image_id}/ai-classification/stats").json()["result_data"]
    assert rd["model"]["id"] == ic.MODEL_ID
    assert rd["dominant_class"] == "INVASIVE"


def test_sin_pesos_devuelve_503(client, monkeypatch):
    def _missing():
        raise ic.ModelUnavailableError("No se encontró el checkpoint")

    monkeypatch.setattr(ai, "get_classifier", _missing)
    image_id, _ = _make_image_with_file("ai_img_nomodel.svs")
    resp = client.post(f"/images/{image_id}/analyze/ai")
    assert resp.status_code == 503
    assert "checkpoint" in resp.json()["detail"]


def test_image_ai_requires_auth(anon_client):
    image_id, _ = _make_image_with_file("ai_img5.svs")
    resp = anon_client.get(f"/images/{image_id}/ai-classification/stats")
    assert resp.status_code in (401, 403)


# --- Endpoints: anotación ----------------------------------------------------

def test_annotation_ai_stats(client):
    image_id, _ = _make_image_with_file("ai_ann1.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/ai-classification/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["annotation_id"] == ann_id
    assert data["analysis_type"] == "ai_classification"
    rd = data["result_data"]
    assert rd["dominant_class"] == "INVASIVE"
    # La anotación (200x150 px) es menor que el campo de entrenamiento.
    assert rd["sampling"]["field_exceeds_region"] is True


def test_annotation_ai_png(client):
    image_id, _ = _make_image_with_file("ai_ann2.svs")
    ann_id = _create_annotation(client, image_id, _RECT)
    resp = client.get(f"/annotations/{ann_id}/ai-classification")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_overlay_cubre_todo_el_tejido_y_nada_del_cristal():
    """Tejido con forma irregular: el color sigue su contorno (sin pintar el
    cristal) y los bordes con poco tejido también se colorean (inferidos)."""
    rgb = np.full((300, 400, 3), 235, dtype=np.uint8)
    mask = np.zeros((300, 400), dtype=bool)
    yy, xx = np.ogrid[:300, :400]
    mask[(yy - 150) ** 2 / 90 ** 2 + (xx - 200) ** 2 / 150 ** 2 <= 1] = True  # elipse
    result = ai.classify_slide_region(
        _FakeSlide("x"), (0, 0, 40000, 30000), rgb, mask, max_patches=5000
    )
    painted = result["overlay"][..., 3] > 0
    assert painted[mask].all()       # el tejido coloreado
    assert not painted[~mask].any()  # nada fuera del tejido
    assert result["inferred_cells"] > 0  # celdas de borde rellenadas


def test_campo_se_centra_en_el_tejido_de_la_celda():
    rgb = np.full((300, 400, 3), 235, dtype=np.uint8)
    mask = np.zeros((300, 400), dtype=bool)
    mask[:, :60] = True  # tejido solo en el tercio izquierdo de la 1ª columna de celdas
    ai.classify_slide_region(
        _FakeSlide("x"), (0, 0, 4000, 3000), rgb, mask, max_patches=5000, min_tissue_frac=0.2
    )
    # Celdas de 1720 px de ancho; el tejido ocupa x < 600: el centro leído se
    # desplaza hacia él en lugar de quedarse en x = 860.
    assert _FakeSlide.centers
    assert all(cx < 400 for cx, _ in _FakeSlide.centers)
