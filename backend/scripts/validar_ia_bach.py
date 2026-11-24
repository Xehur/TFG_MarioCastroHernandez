"""
Valida la clasificación de tejido por IA con WSI de clase conocida: las WSI
anotadas del dataset BACH (ICIAR 2018, parte B), en las que patólogos marcaron
regiones de tejido benigno, carcinoma in situ y carcinoma invasivo.

Para cada región anotada se ejecuta EXACTAMENTE el mismo procedimiento que la
aplicación aplica a una anotación (lectura de la región, máscara de la forma,
detección de tejido y clasificación con ventana deslizante a la escala física
del entrenamiento) y se compara con la etiqueta del patólogo:

- Nivel región: la clase predominante de la región frente a su etiqueta.
- Nivel campo: cada posición analizada dentro de la región frente a la
  etiqueta de la región (aproximación a la concordancia por superficie).

Opcionalmente (``--normal N``) se evalúan también N recuadros por WSI tomados
del tejido NO anotado como clase "Normal". En BACH el tejido sin anotar se
considera normal, pero es una referencia más débil: el informe lo separa.

Las WSI y sus XML se descargan de Kaggle (dataset público CC0) a ``--datos``
y se reutilizan en ejecuciones posteriores. Cada WSI ocupa de 166 a 300 MB.

Uso (desde backend/, sin necesidad de arrancar la aplicación):
    python scripts/validar_ia_bach.py --wsi A03 A07 --normal 10 \\
        --datos ../datos_bach --salida ../docs/evaluacion/validacion_ia

Aviso: el modelo se entrenó con las imágenes de microscopía de BACH (parte A).
Las WSI (parte B) son otra colección, pero el dataset no documenta si hay
pacientes en común; los resultados deben leerse con esa cautela.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from typing import Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image as PILImage, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings  # noqa: E402
from app.services.analysis import ai_classification_service as ai  # noqa: E402
from app.services.analysis.annotation_analysis_service import _shape_mask  # noqa: E402
from app.services.analysis.inception_classifier import get_classifier  # noqa: E402
from app.services.analysis.tissue_detection import detect_tissue  # noqa: E402
from app.services.wsi.openslide_service import OpenSlideService  # noqa: E402
from preparar_ejemplos_bach import (  # noqa: E402
    WSI_ANOTADAS,
    descargar,
    kaggle_url,
    leer_regiones,
)

# Etiqueta del XML de BACH -> código de clase del modelo.
ETIQUETA_A_CODIGO = {
    "benign": "BENIGN",
    "carcinoma in situ": "INSITU",
    "invasive carcinoma": "INVASIVE",
}
CODIGOS = ["NORMAL", "BENIGN", "INSITU", "INVASIVE"]  # orden de presentación
NOMBRES = {c: ai.CLASS_META[c]["name"] for c in CODIGOS}
CARCINOMA = {"INSITU", "INVASIVE"}
_REGION_MAX_SIZE = 2048


# --- Clasificación (mismo procedimiento que una anotación en la aplicación) --

def clasificar_poligono(slide: OpenSlideService, puntos: Sequence[Sequence[int]]) -> Dict:
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    bbox = (min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))
    rgb, scale, used_bbox = slide.read_region_rgb(*bbox, max_size=_REGION_MAX_SIZE)
    mask = _shape_mask(
        "polygon", {"points": [list(p) for p in puntos]}, used_bbox,
        rgb.shape[1], rgb.shape[0], scale,
    )
    if mask is not None:
        rgb = rgb.copy()
        rgb[~mask] = 255
    return _clasificar_region(slide, used_bbox, rgb)


def clasificar_recuadro(slide: OpenSlideService, bbox: Tuple[int, int, int, int]) -> Dict:
    rgb, _, used_bbox = slide.read_region_rgb(*bbox, max_size=_REGION_MAX_SIZE)
    return _clasificar_region(slide, used_bbox, rgb)


def _clasificar_region(slide, used_bbox, rgb) -> Dict:
    tejido = detect_tissue(rgb)
    return ai.classify_slide_region(
        slide, used_bbox, rgb, tejido.mask,
        max_patches=settings.AI_ANNOTATION_MAX_PATCHES,
        target_cells=settings.AI_ANNOTATION_TARGET_CELLS,
    )


def predominante(counts: Dict[str, int]) -> str | None:
    total = sum(counts.values())
    if not total:
        return None
    return max(counts, key=lambda c: counts[c])


# --- Recuadros de tejido normal (sin anotar) ---------------------------------

def recuadros_normales(
    slide: OpenSlideService, regiones, n: int, semilla: int
) -> List[Tuple[int, int, int, int]]:
    """``n`` recuadros de ~2x2 campos sobre tejido sin anotar (con margen)."""
    if n <= 0:
        return []
    thumb, scale = slide.get_thumbnail_rgb(max_size=2048)
    tejido = detect_tissue(thumb).mask
    h, w = tejido.shape
    anotado = PILImage.new("L", (w, h), 0)
    draw = ImageDraw.Draw(anotado)
    for _, puntos in regiones:
        draw.polygon([(x / scale, y / scale) for x, y in puntos], fill=255)
    fw, fh = ai.field_size_level0(slide.get_mpp_x() or ai.DEFAULT_MPP)
    lado_w, lado_h = 2 * fw, 2 * fh
    tw, th = max(1, int(lado_w / scale)), max(1, int(lado_h / scale))
    # Margen de un recuadro alrededor de lo anotado.
    from scipy.ndimage import binary_dilation
    excluir = binary_dilation(np.asarray(anotado) > 0, iterations=max(tw, th))

    rng = np.random.default_rng(semilla)
    candidatos = np.argwhere(tejido & ~excluir)
    rng.shuffle(candidatos)
    elegidos: List[Tuple[int, int, int, int]] = []
    for cy, cx in candidatos:
        y0, x0 = int(cy - th // 2), int(cx - tw // 2)
        if y0 < 0 or x0 < 0 or y0 + th > h or x0 + tw > w:
            continue
        bloque = tejido[y0:y0 + th, x0:x0 + tw]
        if bloque.mean() < 0.6 or excluir[y0:y0 + th, x0:x0 + tw].any():
            continue
        if any(abs(x0 - ex) < tw and abs(y0 - ey) < th for ex, ey, _, _ in elegidos):
            continue
        elegidos.append((x0, y0, tw, th))
        if len(elegidos) >= n:
            break
    return [(int(x * scale), int(y * scale), int(lado_w), int(lado_h)) for x, y, _, _ in elegidos]


# --- Métricas ----------------------------------------------------------------

def matriz_confusion(pares: List[Tuple[str, str]]) -> Dict[str, Dict[str, int]]:
    m = {real: {pred: 0 for pred in CODIGOS} for real in CODIGOS}
    for real, pred in pares:
        if pred is not None:
            m[real][pred] += 1
    return m


def metricas(m: Dict[str, Dict[str, int]]) -> Dict:
    clases_presentes = [c for c in CODIGOS if sum(m[c].values())]
    total = sum(sum(f.values()) for f in m.values())
    aciertos = sum(m[c][c] for c in CODIGOS)
    por_clase = {}
    for c in CODIGOS:
        tp = m[c][c]
        fn = sum(m[c].values()) - tp
        fp = sum(m[r][c] for r in CODIGOS) - tp
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if rec is not None else None)
        por_clase[c] = {"precision": prec, "recall": rec, "f1": f1, "soporte": tp + fn}
    recalls = [por_clase[c]["recall"] for c in clases_presentes]
    # Binario carcinoma (in situ + invasivo) frente a no carcinoma.
    tp = sum(m[r][p] for r in CARCINOMA for p in CARCINOMA)
    fn = sum(m[r][p] for r in CARCINOMA for p in CODIGOS if p not in CARCINOMA)
    fp = sum(m[r][p] for r in CODIGOS if r not in CARCINOMA for p in CARCINOMA)
    tn = total - tp - fn - fp
    return {
        "n": total,
        "exactitud": aciertos / total if total else None,
        "exactitud_equilibrada": float(np.mean(recalls)) if recalls else None,
        "por_clase": por_clase,
        "carcinoma_vs_resto": {
            "sensibilidad": tp / (tp + fn) if tp + fn else None,
            "especificidad": tn / (tn + fp) if tn + fp else None,
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        },
    }


# --- Informe -----------------------------------------------------------------

def _pct(v) -> str:
    return "—" if v is None else f"{100 * v:.1f} %"


def _tabla_confusion(m) -> List[str]:
    cab = "| Real \\ Predicha | " + " | ".join(NOMBRES[c] for c in CODIGOS) + " |"
    lineas = [cab, "|" + "---|" * (len(CODIGOS) + 1)]
    for r in CODIGOS:
        if sum(m[r].values()):
            lineas.append(f"| {NOMBRES[r]} | " + " | ".join(str(m[r][p]) for p in CODIGOS) + " |")
    return lineas


def _bloque(titulo: str, m, met) -> List[str]:
    lineas = [f"### {titulo}", ""]
    lineas += _tabla_confusion(m)
    lineas += ["", f"- Exactitud: **{_pct(met['exactitud'])}** (n = {met['n']})",
               f"- Exactitud equilibrada (media de sensibilidades): {_pct(met['exactitud_equilibrada'])}",
               f"- Carcinoma frente a no carcinoma: sensibilidad {_pct(met['carcinoma_vs_resto']['sensibilidad'])}, "
               f"especificidad {_pct(met['carcinoma_vs_resto']['especificidad'])}", "",
               "| Clase | Precisión | Sensibilidad | F1 | Soporte |", "|---|---|---|---|---|"]
    for c in CODIGOS:
        pc = met["por_clase"][c]
        if pc["soporte"]:
            f1 = "—" if pc["f1"] is None else f"{pc['f1']:.2f}"
            lineas.append(f"| {NOMBRES[c]} | {_pct(pc['precision'])} | {_pct(pc['recall'])} | "
                          f"{f1} | {pc['soporte']} |")
    return lineas + [""]


def escribir_informe(ruta_md: str, res: Dict) -> None:
    l = ["# Validación de la clasificación IA con WSI de BACH", "",
         f"Fecha: {res['fecha']} · WSI: {', '.join(res['wsi'])} · "
         f"Modelo: {res['modelo'].get('id')} ({res['modelo'].get('device')}) · "
         f"Tiempo total: {res['segundos']:.0f} s", "",
         "Referencia: regiones anotadas por patólogos en las WSI de BACH (parte B). "
         "Cada región se clasificó con el mismo procedimiento que una anotación en la aplicación "
         "(ventana deslizante a la escala física del entrenamiento).", ""]
    for clave, titulo in (("anotadas", "Regiones anotadas por patólogos"),
                          ("todas", "Regiones anotadas + recuadros de tejido sin anotar (Normal)")):
        bloque = res["evaluaciones"].get(clave)
        if not bloque:
            continue
        l += [f"## {titulo}", ""]
        l += _bloque("Nivel región (clase predominante)", bloque["region"]["matriz"], bloque["region"]["metricas"])
        l += _bloque("Nivel campo (cada posición analizada)", bloque["campo"]["matriz"], bloque["campo"]["metricas"])
    l += ["## Limitaciones", "",
          "- El modelo se entrenó con imágenes de microscopía de BACH (parte A); BACH no documenta si "
          "las WSI de la parte B comparten pacientes con ellas.",
          "- La etiqueta de una región se asigna a todas sus posiciones, aunque una región anotada "
          "puede incluir estroma u otros tejidos.",
          "- El tejido sin anotar se toma como «Normal», que es una referencia más débil.",
          "- Muestra pequeña (pocas WSI): los porcentajes tienen una incertidumbre alta.", ""]
    with open(ruta_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(l))


# --- Programa principal ------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Valida la clasificación IA con las WSI anotadas de BACH.")
    p.add_argument("--wsi", nargs="+", default=["A03", "A07"],
                   help="Códigos de WSI anotadas (A01-A10). Por defecto: A03 A07")
    p.add_argument("--datos", default="datos_bach", help="Carpeta de descargas (se reutiliza)")
    p.add_argument("--normal", type=int, default=0,
                   help="Recuadros de tejido sin anotar por WSI evaluados como Normal")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--salida", default="validacion_ia", help="Prefijo de los ficheros .json y .md")
    args = p.parse_args()

    validos = {c for c, _ in WSI_ANOTADAS}
    for c in args.wsi:
        if c not in validos:
            raise SystemExit(f"WSI desconocida: {c}. Válidas: {', '.join(sorted(validos))}")
    os.makedirs(args.datos, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)

    modelo = get_classifier().info()
    t0 = time.time()
    detalle, pares = [], {"region": [], "campo": [], "region_n": [], "campo_n": []}
    for codigo in args.wsi:
        svs = os.path.join(args.datos, f"{codigo}.svs")
        xml = os.path.join(args.datos, f"{codigo}.xml")
        if not os.path.isfile(svs):
            descargar(kaggle_url(f"{codigo}.svs"), svs, f"Descargando {codigo}.svs")
        if not os.path.isfile(xml):
            descargar(kaggle_url(f"{codigo}.xml"), xml, f"Descargando {codigo}.xml")
        regiones = leer_regiones(xml)
        slide = OpenSlideService(svs)
        try:
            print(f"{codigo}: {len(regiones)} regiones anotadas", flush=True)
            casos = [(ETIQUETA_A_CODIGO[e], "anotada", pts) for e, pts in regiones]
            casos += [("NORMAL", "sin_anotar", bb)
                      for bb in recuadros_normales(slide, regiones, args.normal, args.semilla)]
            for i, (real, tipo, geom) in enumerate(casos, 1):
                r = clasificar_poligono(slide, geom) if tipo == "anotada" else clasificar_recuadro(slide, geom)
                counts = r["counts"]
                pred = predominante(counts)
                etiquetas = [ai.CLASS_CODES[k] for k in np.asarray(r["labels"]).ravel() if k >= 0]
                detalle.append({"wsi": codigo, "tipo": tipo, "real": real, "predicha": pred,
                                "recuentos": counts, "posiciones": len(etiquetas),
                                "prob_media": r["mean_probabilities"]})
                clave = "" if tipo == "anotada" else "_n"
                pares["region" + clave].append((real, pred))
                pares["campo" + clave] += [(real, e) for e in etiquetas]
                print(f"  [{i}/{len(casos)}] {NOMBRES[real]:<18} -> "
                      f"{NOMBRES.get(pred, 'sin tejido'):<18} {dict(Counter(etiquetas))}", flush=True)
        finally:
            slide.close()

    def evaluar(region, campo):
        mr, mc = matriz_confusion(region), matriz_confusion(campo)
        return {"region": {"matriz": mr, "metricas": metricas(mr)},
                "campo": {"matriz": mc, "metricas": metricas(mc)}}

    evaluaciones = {"anotadas": evaluar(pares["region"], pares["campo"])}
    if pares["region_n"]:
        evaluaciones["todas"] = evaluar(pares["region"] + pares["region_n"],
                                        pares["campo"] + pares["campo_n"])
    res = {"fecha": time.strftime("%Y-%m-%d"), "wsi": args.wsi, "modelo": modelo,
           "parametros": {"normal_por_wsi": args.normal, "semilla": args.semilla,
                          "objetivo_celdas": settings.AI_ANNOTATION_TARGET_CELLS,
                          "max_campos": settings.AI_ANNOTATION_MAX_PATCHES},
           "segundos": time.time() - t0, "evaluaciones": evaluaciones, "detalle": detalle}
    with open(args.salida + ".json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    escribir_informe(args.salida + ".md", res)
    met = evaluaciones["anotadas"]["region"]["metricas"]
    print(f"\nExactitud por región (anotadas): {_pct(met['exactitud'])} · "
          f"informe en {args.salida}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
