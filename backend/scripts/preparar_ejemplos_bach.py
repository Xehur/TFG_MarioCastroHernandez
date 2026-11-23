"""
Descarga WSI de ejemplo del dataset BACH (ICIAR 2018) y las importa en la
aplicación, junto con las anotaciones de los patólogos.

Fuente: https://www.kaggle.com/datasets/truthisneverlinear/bach-breast-cancer-histology-images
(licencia CC0). El dataset completo ocupa 18 GB; este script descarga solo las
WSI anotadas A01–A10 que se pidan (de ~170 a ~300 MB cada una), de una en una y
sin necesidad de cuenta de Kaggle.

Para cada WSI:
  1. La descarga (Kaggle la sirve comprimida en .zip) y la descomprime.
  2. La sube a tu cuenta con la API de la aplicación (POST /images/upload).
  3. Importa las regiones anotadas por patólogos (XML de Aperio ImageScope) como
     anotaciones de tipo polígono con las clases "Benigno", "Carcinoma in situ"
     y "Carcinoma invasivo" (se crean si no existen).

Uso con Docker (desde la carpeta docker/, con la aplicación arrancada):
    .\\preparar_ejemplos.ps1            (Windows)
    sh preparar_ejemplos.sh             (Linux / macOS)

Uso directo (desarrollo, desde backend/):
    python scripts/preparar_ejemplos_bach.py --count 2
"""
from __future__ import annotations

import argparse
import getpass
import os
import shutil
import sys
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

import httpx

KAGGLE_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/"
    "truthisneverlinear/bach-breast-cancer-histology-images/"
)
WSI_DIR = "ICIAR2018_BACH_Challenge/ICIAR2018_BACH_Challenge/WSI/"

# WSI anotadas, de menor a mayor tamaño (MB aproximados de descarga).
WSI_ANOTADAS = [
    ("A03", 166), ("A07", 187), ("A05", 210), ("A09", 215), ("A10", 215),
    ("A06", 231), ("A08", 236), ("A02", 238), ("A01", 266), ("A04", 300),
]

# Etiqueta del XML -> (clase en la aplicación, color). Mismos colores que la IA.
CLASES = {
    "benign": ("Benigno", "#3b82f6"),
    "carcinoma in situ": ("Carcinoma in situ", "#f59e0b"),
    "invasive carcinoma": ("Carcinoma invasivo", "#dc2626"),
}
MAX_VERTICES = 200  # se simplifican los contornos muy detallados


def kaggle_url(nombre: str) -> str:
    return KAGGLE_URL + urllib.parse.quote(WSI_DIR + nombre, safe="")


def descargar(url: str, destino: str, etiqueta: str) -> None:
    """Descarga con barra de progreso; si llega un .zip, extrae su contenido."""
    temporal = destino + ".part"
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        if r.status_code != 200:
            raise RuntimeError(f"Kaggle respondió {r.status_code} al descargar {etiqueta}")
        total = int(r.headers.get("content-length") or 0)
        hecho, ultimo = 0, 0.0
        with open(temporal, "wb") as fh:
            for bloque in r.iter_bytes(1024 * 1024):
                fh.write(bloque)
                hecho += len(bloque)
                if total > 5e6 and time.time() - ultimo > 0.5:
                    ultimo = time.time()
                    print(f"\r    {etiqueta}: {hecho / 1e6:6.0f} / {total / 1e6:.0f} MB "
                          f"({100 * hecho / total:3.0f} %)", end="", flush=True)
    if total > 5e6:
        print(f"\r    {etiqueta}: {hecho / 1e6:6.0f} / {total / 1e6:.0f} MB (100 %)")
    else:
        print(f"    {etiqueta}: {hecho / 1e3:.0f} KB")
    if zipfile.is_zipfile(temporal):
        with zipfile.ZipFile(temporal) as z:
            miembro = next(n for n in z.namelist() if not n.endswith("/"))
            with z.open(miembro) as src, open(destino, "wb") as dst:
                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
        os.remove(temporal)
    else:
        os.replace(temporal, destino)


def leer_regiones(ruta_xml: str) -> list[tuple[str, list[list[int]]]]:
    """Regiones (etiqueta, puntos) de un XML de Aperio ImageScope."""
    regiones = []
    for region in ET.parse(ruta_xml).getroot().iter("Region"):
        texto = (region.get("Text") or "").strip().lower()
        puntos = [
            [int(float(v.get("X"))), int(float(v.get("Y")))]
            for v in region.iter("Vertex")
        ]
        if texto in CLASES and len(puntos) >= 3:
            paso = max(1, -(-len(puntos) // MAX_VERTICES))  # división hacia arriba
            regiones.append((texto, puntos[::paso]))
    return regiones


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.c = httpx.Client(timeout=60)

    def login(self, email: str, password: str) -> str:
        r = self.c.post(f"{self.base}/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise SystemExit("No se pudo iniciar sesión: revisa el email y la contraseña.")
        self.c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        return r.json()["user"].get("full_name") or email

    def imagenes(self) -> dict[str, int]:
        r = self.c.get(f"{self.base}/images/", params={"limit": 1000})
        r.raise_for_status()
        return {i["filename"]: i["id"] for i in r.json()}

    def subir(self, ruta: str, nombre: str) -> int:
        with open(ruta, "rb") as fh:
            r = self.c.post(
                f"{self.base}/images/upload",
                files={"file": (nombre, fh, "application/octet-stream")},
                timeout=1800,
            )
        if r.status_code != 201:
            raise RuntimeError(f"error {r.status_code} al subir {nombre}: {r.text[:200]}")
        return r.json()["id"]

    def clases(self) -> dict[str, int]:
        respuesta = self.c.get(f"{self.base}/annotation-classes").json()
        existentes = {c["name"]: c["id"] for c in respuesta}
        for nombre, color in CLASES.values():
            if nombre not in existentes:
                r = self.c.post(f"{self.base}/annotation-classes", json={
                    "name": nombre, "color": color,
                    "description": "Anotada por patólogos (dataset BACH)",
                })
                r.raise_for_status()
                existentes[nombre] = r.json()["id"]
        return existentes

    def anotar(self, image_id: int, regiones, ids_clase: dict[str, int]) -> int:
        n = 0
        for texto, puntos in regiones:
            nombre, color = CLASES[texto]
            r = self.c.post(f"{self.base}/images/{image_id}/annotations", json={
                "shape_type": "polygon",
                "coordinates": {"points": puntos},
                "color": color,
                "label": "Patólogo",  # la clase indica el tipo de lesión
                "class_id": ids_clase[nombre],
            })
            r.raise_for_status()
            n += 1
        return n


def main() -> int:
    p = argparse.ArgumentParser(description="Importa WSI de ejemplo del dataset BACH.")
    p.add_argument("--count", type=int, default=2,
                   help="Número de WSI a importar (1-10, por defecto 2: ~350 MB)")
    p.add_argument("--email", help="Email de tu cuenta en la aplicación")
    p.add_argument("--password", help="Contraseña (si no se indica, se pregunta)")
    p.add_argument("--api", default=os.environ.get("EJEMPLOS_API", "http://localhost:8000"),
                   help="URL del backend (por defecto http://localhost:8000)")
    p.add_argument("--sin-anotaciones", action="store_true",
                   help="No importar las anotaciones de los patólogos")
    p.add_argument("--descargas", help="Carpeta donde guardar y reutilizar las descargas "
                                       "(por defecto, una temporal que se borra al terminar)")
    args = p.parse_args()

    if not 1 <= args.count <= len(WSI_ANOTADAS):
        raise SystemExit(f"--count debe estar entre 1 y {len(WSI_ANOTADAS)}")
    elegidas = WSI_ANOTADAS[: args.count]
    total_mb = sum(mb for _, mb in elegidas)

    print("Ejemplos del dataset BACH (ICIAR 2018, licencia CC0)")
    print(f"Se importarán {args.count} WSI: {', '.join(n for n, _ in elegidas)} "
          f"(~{total_mb} MB de descarga).\n")

    email = args.email or input("Email de tu cuenta en la aplicación: ").strip()
    password = args.password or getpass.getpass("Contraseña: ")
    api = Api(args.api)
    try:
        nombre_usuario = api.login(email, password)
    except httpx.ConnectError:
        raise SystemExit(f"No se puede conectar con la aplicación en {args.api}. ¿Está arrancada?")
    print(f"Sesión iniciada como {nombre_usuario}.\n")

    existentes = api.imagenes()
    ids_clase = {} if args.sin_anotaciones else api.clases()

    carpeta = args.descargas or tempfile.mkdtemp(prefix="bach_")
    os.makedirs(carpeta, exist_ok=True)
    importadas, errores = 0, 0
    try:
        for i, (codigo, mb) in enumerate(elegidas, 1):
            nombre = f"BACH_{codigo}.svs"
            print(f"[{i}/{len(elegidas)}] {nombre} (~{mb} MB)")
            if nombre in existentes:
                print("    Ya está en tu cuenta: se omite.\n")
                continue
            try:
                ruta_svs = os.path.join(carpeta, f"{codigo}.svs")
                if not os.path.isfile(ruta_svs):
                    descargar(kaggle_url(f"{codigo}.svs"), ruta_svs, "Descargando WSI")
                print("    Subiendo a la aplicación…", flush=True)
                image_id = api.subir(ruta_svs, nombre)
                if not args.sin_anotaciones:
                    ruta_xml = os.path.join(carpeta, f"{codigo}.xml")
                    if not os.path.isfile(ruta_xml):
                        descargar(kaggle_url(f"{codigo}.xml"), ruta_xml, "Descargando anotaciones")
                    n = api.anotar(image_id, leer_regiones(ruta_xml), ids_clase)
                    print(f"    {n} regiones anotadas por patólogos importadas.")
                print("    Listo.\n")
                importadas += 1
            except Exception as exc:  # noqa: BLE001  (se continúa con la siguiente)
                errores += 1
                print(f"\n    ERROR: {exc}\n")
    finally:
        if not args.descargas:
            shutil.rmtree(carpeta, ignore_errors=True)

    print(f"Terminado: {importadas} WSI importadas"
          + (f", {errores} con error." if errores else "."))
    print("Ábrelas desde la galería de la aplicación (http://localhost:5173).")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
