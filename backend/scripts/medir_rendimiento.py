"""
Mide el rendimiento de los servicios del backend sobre WSI reales.

Invoca directamente los mismos servicios que usan los endpoints (sin HTTP):
  - apertura de la WSI y creación del generador Deep Zoom;
  - generación de 100 teselas aleatorias (lectura + JPEG) en el nivel de máxima
    resolución y en un nivel intermedio con reducción 1:8;
  - miniatura, detección de tejido y mapa de densidad (rejilla de 256 px);
  - clasificación con InceptionV3 de la imagen completa.

Los resultados se imprimen por pantalla y se guardan en JSON.

Uso (desde backend/):
    python scripts/medir_rendimiento.py ruta/a/imagen1.svs ruta/a/imagen2.svs
    python scripts/medir_rendimiento.py --salida resultados.json imagen.svs
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.services.analysis import ai_classification_service as ai  # noqa: E402
from app.services.analysis.density_generation import generate_density_map  # noqa: E402
from app.services.analysis.inception_classifier import get_classifier  # noqa: E402
from app.services.analysis.tissue_detection import detect_tissue  # noqa: E402
from app.services.wsi.openslide_service import OpenSlideService  # noqa: E402

N_TESELAS = 100
REJILLA_DENSIDAD = 256


def _percentil(valores, p):
    v = sorted(valores)
    k = (len(v) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def _resumen_ms(valores):
    return {
        "n": len(valores),
        "media_ms": round(statistics.mean(valores) * 1000, 1),
        "mediana_ms": round(statistics.median(valores) * 1000, 1),
        "p95_ms": round(_percentil(valores, 95) * 1000, 1),
    }


def _medir_teselas(dz, nivel):
    cols, rows = dz.level_tiles[nivel]
    tiempos = []
    for _ in range(N_TESELAS):
        c, r = random.randrange(cols), random.randrange(rows)
        t = time.perf_counter()
        buf = io.BytesIO()
        dz.get_tile(nivel, (c, r)).convert("RGB").save(buf, "JPEG", quality=80)
        tiempos.append(time.perf_counter() - t)
    return _resumen_ms(tiempos)


def medir(ruta):
    r = {"archivo": os.path.basename(ruta), "tam_MB": round(os.path.getsize(ruta) / 1e6, 1)}

    t = time.perf_counter()
    slide = OpenSlideService(ruta)
    r["apertura_ms"] = round((time.perf_counter() - t) * 1000, 1)
    try:
        w, h = slide.get_dimensions()
        r.update(dimensiones=[w, h], niveles=slide.slide.level_count,
                 mpp=slide.get_mpp_x(), megapixeles=round(w * h / 1e6))

        dz = slide.get_deepzoom_generator()
        r["tesela_max"] = _medir_teselas(dz, dz.level_count - 1)
        r["tesela_1_8"] = _medir_teselas(dz, dz.level_count - 4)

        t = time.perf_counter()
        rgb, escala = slide.get_thumbnail_rgb(2048)
        r["miniatura_s"] = round(time.perf_counter() - t, 2)

        t = time.perf_counter()
        tejido = detect_tissue(rgb)
        r["tejido_s"] = round(time.perf_counter() - t, 2)
        r["tejido_pct"] = round(tejido.tissue_percent, 2)

        t = time.perf_counter()
        dens = generate_density_map(tejido.mask, REJILLA_DENSIDAD, w, h)
        r["densidad_s"] = round(time.perf_counter() - t, 3)
        r["densidad_celdas"] = [dens.rows, dens.cols]

        th, tw = rgb.shape[:2]
        bbox = (0, 0, int(round(tw * escala)), int(round(th * escala)))
        t = time.perf_counter()
        res = ai.classify_slide_region(slide, bbox, rgb, tejido.mask)
        t_ia = time.perf_counter() - t
        r.update(
            ia_s=round(t_ia, 1),
            ia_campos_tejido=res["tissue_cells"],
            ia_campos_analizados=res["tissue_patches"],
            ia_cobertura=res["coverage"],
            ia_campos_por_s=round(res["tissue_patches"] / t_ia, 2) if t_ia else None,
            ia_conteos=res["counts"],
            ia_conf_media=round(res["mean_confidence"], 3),
        )
    finally:
        slide.close()
    return r


def main() -> int:
    p = argparse.ArgumentParser(description="Mide el rendimiento del backend sobre WSI reales.")
    p.add_argument("imagenes", nargs="+", help="Rutas de las WSI a medir")
    p.add_argument("--salida", default="resultados_rendimiento.json",
                   help="Fichero JSON de resultados")
    p.add_argument("--semilla", type=int, default=42, help="Semilla de las teselas aleatorias")
    args = p.parse_args()
    random.seed(args.semilla)

    t = time.perf_counter()
    info_modelo = get_classifier().info()
    salida = {
        "modelo": info_modelo,
        "carga_modelo_s": round(time.perf_counter() - t, 2),
        "configuracion": {
            "AI_DEVICE": settings.AI_DEVICE,
            "AI_MAX_PATCHES": settings.AI_MAX_PATCHES,
            "AI_BATCH_SIZE": settings.AI_BATCH_SIZE,
            "AI_READ_WORKERS": settings.AI_READ_WORKERS,
        },
        "wsi": [],
    }
    for ruta in args.imagenes:
        r = medir(ruta)
        salida["wsi"].append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)

    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    print(f"Resultados guardados en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
