"""
Smoke test (CPU o GPU) del checkpoint InceptionV3 (tejido mamario, BACH).

Comprueba que:
  1. El checkpoint carga con ``weights_only=True`` y encaja con la arquitectura.
  2. La salida tiene forma (N, 4), es finita y suma 1 por fila.
  3. El wrapper del backend reproduce el pipeline de referencia de torchvision.

Opcionalmente, con ``--images``, clasifica imágenes reales. Si la carpeta tiene
subcarpetas con el nombre de la clase (``Benign/``, ``InSitu/``, ``Invasive/``,
``Normal/``, como el dataset BACH), calcula la exactitud con
``transform_input=True`` (como en el entrenamiento) y ``False`` (como
``InceptionV3/src/inference.py``), para confirmar cuál es el correcto.

Uso (desde ``backend/``):
    python scripts/smoke_inception.py
    python scripts/smoke_inception.py --images C:/ruta/BACH/Photos --limit 40
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.services.analysis.inception_classifier import (  # noqa: E402
    MODEL_CLASSES,
    InceptionClassifier,
)

_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


def _collect(root: str, limit: int):
    """Devuelve [(ruta, etiqueta|None)], con como mucho ``limit`` por clase."""
    items = []
    subdirs = sorted(
        d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))
    )
    labelled = [d for d in subdirs if d.lower() in MODEL_CLASSES]
    if labelled:
        for d in labelled:
            files = sorted(
                f for f in os.listdir(os.path.join(root, d)) if f.lower().endswith(_EXTS)
            )[:limit]
            items += [(os.path.join(root, d, f), d.lower()) for f in files]
    else:
        files = sorted(f for f in os.listdir(root) if f.lower().endswith(_EXTS))[:limit]
        items = [(os.path.join(root, f), None) for f in files]
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--weights", default=settings.INCEPTION_WEIGHTS_PATH)
    parser.add_argument("--images", help="Imagen o carpeta de imágenes de prueba")
    parser.add_argument("--limit", type=int, default=25, help="Máx. imágenes por clase")
    parser.add_argument(
        "--device", default=settings.AI_DEVICE, help="cpu, cuda/gpu o auto (por defecto AI_DEVICE)"
    )
    args = parser.parse_args()

    import torch
    from PIL import Image

    torch.manual_seed(0)
    clf = InceptionClassifier(
        args.weights, device=args.device, expected_sha256=settings.INCEPTION_WEIGHTS_SHA256
    ).load()
    print(f"[OK] Checkpoint cargado: {args.weights}")
    print(f"     sha256={clf.sha256}")
    matches = clf.sha256 == settings.INCEPTION_WEIGHTS_SHA256
    print(f"     sha256 esperado: {'coincide' if matches else 'NO coincide'}")
    print(f"     clases={MODEL_CLASSES}  transform_input={clf._model.transform_input}")
    print(f"     dispositivo={clf.device}" + (f" ({clf.gpu_name})" if clf.gpu_name else ""))

    # Imagen sintética reproducible (H&E aproximado).
    rng = np.random.default_rng(0)
    synth = [
        np.clip(rng.normal((180, 110, 170), 30, size=(1536, 2048, 3)), 0, 255).astype(np.uint8)
        for _ in range(4)
    ]
    t0 = time.perf_counter()
    probs = clf.predict_batch(synth)
    dt = time.perf_counter() - t0
    assert probs.shape == (4, 4), probs.shape
    assert np.isfinite(probs).all()
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-4)
    print(
        "[OK] Salida (N,4) finita, filas suman 1. "
        f"{dt / 4 * 1000:.0f} ms/imagen en {clf.device.upper()}"
    )

    # Referencia independiente con torchvision (mismo pipeline que finetune.py).
    from torchvision import transforms

    ref_tf = transforms.Compose(
        [
            transforms.Resize((299, 299)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    x = torch.stack([ref_tf(Image.fromarray(a)) for a in synth]).to(clf.device)
    with torch.inference_mode():
        ref = torch.softmax(clf._model(x), dim=1).cpu().numpy()
    max_diff = float(np.abs(ref - probs).max())
    # En GPU hay pequeñas diferencias numéricas respecto a la CPU.
    assert max_diff < (1e-5 if clf.device == "cpu" else 1e-3), max_diff
    print(f"[OK] Wrapper == referencia torchvision (máx. dif. {max_diff:.2e})")

    if not args.images:
        return 0

    items = (
        [(args.images, None)]
        if os.path.isfile(args.images)
        else _collect(args.images, args.limit)
    )
    if not items:
        print("No se encontraron imágenes.")
        return 1

    imgs = [Image.open(p).convert("RGB") for p, _ in items]
    results = {}
    for flag in (True, False):
        clf._model.transform_input = flag
        results[flag] = clf.predict_batch(imgs).argmax(axis=1)
    clf._model.transform_input = True

    labels = [lbl for _, lbl in items]
    if all(lbl is not None for lbl in labels):
        y = np.array([MODEL_CLASSES.index(lbl) for lbl in labels])
        for flag, pred in results.items():
            acc = float((pred == y).mean())
            print(f"transform_input={flag!s:5}: exactitud {acc:.3f} sobre {len(y)} imágenes")
        print("(Nota: si son imágenes del entrenamiento la exactitud está sesgada al alza.)")
    else:
        for (path, _), a, b in zip(items, results[True], results[False]):
            print(
                f"{os.path.basename(path)}: {MODEL_CLASSES[a]} "
                f"(transform_input=False -> {MODEL_CLASSES[b]})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
