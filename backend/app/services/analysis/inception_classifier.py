"""
Clasificador InceptionV3 de tejido mamario H&E (dataset BACH / ICIAR 2018).

Encapsula la carga del checkpoint ``HE_inceptionv3.pth`` y la inferencia por
lotes, con el MISMO preprocesado que se usó en validación durante el
entrenamiento (``InceptionV3/src/finetune.py``):

    RGB -> Resize((299, 299)) -> ToTensor() -> Normalize(ImageNet)

Detalle importante: en el entrenamiento el modelo se creó con
``inception_v3(weights='IMAGENET1K_V1')``, y torchvision activa en ese caso
``transform_input=True`` (re-normaliza internamente la entrada al rango que
esperaban los pesos originales de Google). ``inference.py`` crea el modelo con
``weights=None`` y lo deja en ``False``, por lo que NO reproduce el
entrenamiento. Aquí se fija ``transform_input=True`` de forma explícita.

Salidas del modelo (orden exacto, ``ImageFolder`` ordena alfabéticamente):
``benign``, ``insitu``, ``invasive``, ``normal``. El "fondo" NO es una salida
de la red: es la etiqueta de las celdas que no se analizan.

Uso académico / de investigación. Las probabilidades softmax no están
calibradas y no constituyen un diagnóstico clínico.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from PIL import Image as PILImage

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "inceptionv3-bach-he"
MODEL_ARCH = "inception_v3"
MODEL_DATASET = "BACH (ICIAR 2018) Photos"
PREPROCESSING_VERSION = "bach-v1"  # Resize 299x299 + ImageNet norm + transform_input

# Orden EXACTO de las salidas del modelo.
MODEL_CLASSES: List[str] = ["benign", "insitu", "invasive", "normal"]
NUM_CLASSES = len(MODEL_CLASSES)
MODEL_INPUT_SIZE = 299
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

SUPPORTED_DEVICES = ("cpu",)


class ModelUnavailableError(RuntimeError):
    """El checkpoint no existe, no es legible o no encaja con la arquitectura."""


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_device(requested: str) -> str:
    requested = (requested or "cpu").lower()
    if requested == "auto":
        return "cpu"
    if requested not in SUPPORTED_DEVICES:
        logger.warning(
            "AI_DEVICE=%s no está soportado todavía; se usa CPU.", requested
        )
        return "cpu"
    return requested


def to_rgb_uint8(image: Any) -> np.ndarray:
    """Normaliza una entrada (PIL o ndarray gris/RGB/RGBA) a RGB uint8 (H, W, 3)."""
    if isinstance(image, PILImage.Image):
        return np.asarray(image.convert("RGB"), dtype=np.uint8)
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.ndim == 3 and arr.shape[-1] == 4:
        arr = arr[..., :3]
    elif arr.ndim != 3 or arr.shape[-1] != 3:
        raise ValueError(f"Forma de imagen no soportada: {arr.shape}")
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)


class InceptionClassifier:
    """Envoltorio de inferencia de InceptionV3 (4 clases)."""

    def __init__(
        self,
        weights_path: str,
        device: str = "cpu",
        expected_sha256: Optional[str] = None,
    ):
        self.weights_path = weights_path
        self.device = _resolve_device(device)
        self.expected_sha256 = (expected_sha256 or "").lower() or None
        self.sha256: Optional[str] = None
        self._model = None
        self._transform = None

    # --- Carga ---------------------------------------------------------------

    def load(self) -> "InceptionClassifier":
        import torch
        import torch.nn as nn
        from torchvision import models, transforms

        path = self.weights_path
        if not path or not os.path.isfile(path):
            raise ModelUnavailableError(
                f"No se encontró el checkpoint de InceptionV3 en '{path}'. "
                "Configure INCEPTION_WEIGHTS_PATH."
            )

        self.sha256 = _sha256(path)
        if self.expected_sha256 and self.sha256 != self.expected_sha256:
            logger.warning(
                "SHA-256 del checkpoint (%s) distinto del esperado (%s).",
                self.sha256,
                self.expected_sha256,
            )

        model = models.inception_v3(
            weights=None, aux_logits=True, init_weights=False, transform_input=True
        )
        model.AuxLogits.fc = nn.Linear(model.AuxLogits.fc.in_features, NUM_CLASSES)
        model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)

        try:
            state = torch.load(path, map_location="cpu", weights_only=True)
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            state = {k.removeprefix("module."): v for k, v in state.items()}
            model.load_state_dict(state, strict=True)
        except Exception as exc:  # noqa: BLE001
            raise ModelUnavailableError(
                f"El checkpoint '{path}' no es compatible con InceptionV3 de "
                f"{NUM_CLASSES} clases: {exc}"
            ) from exc

        model.eval()
        model.to(self.device)
        self._model = model
        self._transform = transforms.Compose(
            [
                transforms.Resize((MODEL_INPUT_SIZE, MODEL_INPUT_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )
        logger.info(
            "InceptionV3 cargado desde %s (sha256=%s, device=%s)",
            path,
            self.sha256[:12],
            self.device,
        )
        return self

    # --- Inferencia ----------------------------------------------------------

    def preprocess(self, images: Sequence[Any]):
        """Lista de imágenes -> tensor (N, 3, 299, 299) normalizado."""
        import torch

        tensors = [
            self._transform(PILImage.fromarray(to_rgb_uint8(img), mode="RGB"))
            for img in images
        ]
        return torch.stack(tensors)

    def predict_batch(self, images: Sequence[Any], batch_size: int = 16) -> np.ndarray:
        """Devuelve las probabilidades softmax (N, 4) en el orden ``MODEL_CLASSES``."""
        import torch

        if self._model is None:
            self.load()
        if len(images) == 0:
            return np.zeros((0, NUM_CLASSES), dtype=np.float32)

        outputs: List[np.ndarray] = []
        with torch.inference_mode():
            for i in range(0, len(images), batch_size):
                batch = self.preprocess(images[i : i + batch_size]).to(self.device)
                logits = self._model(batch)
                outputs.append(torch.softmax(logits, dim=1).cpu().numpy())
        return np.concatenate(outputs, axis=0).astype(np.float32)

    def info(self) -> Dict[str, Any]:
        return {
            "id": MODEL_ID,
            "arch": MODEL_ARCH,
            "dataset": MODEL_DATASET,
            "classes": list(MODEL_CLASSES),
            "input_size": MODEL_INPUT_SIZE,
            "preprocessing_version": PREPROCESSING_VERSION,
            "weights_sha256": self.sha256,
            "device": self.device,
        }


_classifier: Optional[InceptionClassifier] = None
_lock = threading.Lock()


def get_classifier() -> InceptionClassifier:
    """Carga (perezosamente, una vez por proceso) y devuelve el clasificador."""
    global _classifier
    if _classifier is None:
        with _lock:
            if _classifier is None:
                _classifier = InceptionClassifier(
                    settings.INCEPTION_WEIGHTS_PATH,
                    device=settings.AI_DEVICE,
                    expected_sha256=settings.INCEPTION_WEIGHTS_SHA256,
                ).load()
    return _classifier
