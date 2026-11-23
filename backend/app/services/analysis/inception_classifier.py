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

Dispositivo (``AI_DEVICE``): ``cpu`` (por defecto), ``cuda``/``gpu`` (GPU NVIDIA
con CUDA o AMD con ROCm; PyTorch usa el mismo dispositivo para ambas) o
``auto``. Si se pide GPU y no está disponible o falla, se usa CPU con un aviso.

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

# Valores admitidos en AI_DEVICE. PyTorch expone tanto las GPU NVIDIA (CUDA)
# como las AMD (ROCm) con el mismo dispositivo "cuda", así que "gpu", "cuda" y
# "rocm" se resuelven igual; el backend real se indica en ``gpu_info()``.
SUPPORTED_DEVICES = ("cpu", "cuda", "auto")
_DEVICE_ALIASES = {"gpu": "cuda", "rocm": "cuda", "nvidia": "cuda", "amd": "cuda"}


class ModelUnavailableError(RuntimeError):
    """El checkpoint no existe, no es legible o no encaja con la arquitectura."""


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gpu_available() -> bool:
    """True si PyTorch ve una GPU utilizable (NVIDIA con CUDA o AMD con ROCm)."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001  (PyTorch ausente o mal instalado)
        return False


def _resolve_device(requested: str) -> str:
    """Traduce ``AI_DEVICE`` al dispositivo real de PyTorch.

    - ``cpu``: siempre CPU.
    - ``cuda`` / ``gpu`` / ``rocm``: GPU si está disponible; si no, CPU con aviso
      (la aplicación sigue funcionando, solo más despacio).
    - ``auto``: GPU si está disponible, si no CPU.
    """
    requested = (requested or "cpu").strip().lower()
    requested = _DEVICE_ALIASES.get(requested, requested)
    if requested not in SUPPORTED_DEVICES:
        logger.warning("AI_DEVICE=%s no es válido; se usa CPU.", requested)
        return "cpu"
    if requested == "cpu":
        return "cpu"
    if _gpu_available():
        return "cuda"
    if requested == "cuda":
        logger.warning(
            "AI_DEVICE=%s pero PyTorch no detecta ninguna GPU (¿imagen de "
            "Docker CPU, GPU no expuesta al contenedor o drivers?); se usa CPU.",
            requested,
        )
    return "cpu"


def gpu_info() -> Dict[str, Any]:
    """Diagnóstico de PyTorch y de la GPU, sin cargar el modelo."""
    info: Dict[str, Any] = {
        "torch_version": None,
        "build": None,
        "gpu_available": False,
        "gpu_name": None,
    }
    try:
        import torch
    except Exception:  # noqa: BLE001
        return info
    info["torch_version"] = torch.__version__
    if getattr(torch.version, "hip", None):
        info["build"] = f"rocm {torch.version.hip}"
    elif getattr(torch.version, "cuda", None):
        info["build"] = f"cuda {torch.version.cuda}"
    else:
        info["build"] = "cpu"
    if _gpu_available():
        info["gpu_available"] = True
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception:  # noqa: BLE001
            pass
    return info


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
        self.requested_device = (device or "cpu").strip().lower()
        self.device = _resolve_device(device)
        self.gpu_name: Optional[str] = None
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
        model = self._move_to_device(model)
        self._model = model
        self._transform = transforms.Compose(
            [
                transforms.Resize((MODEL_INPUT_SIZE, MODEL_INPUT_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )
        logger.info(
            "InceptionV3 cargado desde %s (sha256=%s, AI_DEVICE=%s -> %s%s)",
            path,
            self.sha256[:12],
            self.requested_device,
            self.device,
            f" [{self.gpu_name}]" if self.gpu_name else "",
        )
        return self

    def _move_to_device(self, model):
        """Lleva el modelo a la GPU y hace una inferencia de prueba. Si la GPU
        falla (p. ej. arquitectura no soportada por la versión de ROCm/CUDA),
        vuelve a CPU para que la aplicación siga funcionando."""
        import torch

        if self.device == "cpu":
            return model.to("cpu")
        try:
            model = model.to(self.device)
            with torch.inference_mode():
                dummy = torch.zeros(1, 3, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE)
                model(dummy.to(self.device))
            torch.cuda.synchronize()
            self.gpu_name = torch.cuda.get_device_name(0)
            return model
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "No se pudo usar la GPU (%s); la IA se ejecutará en CPU.", exc
            )
            self.device = "cpu"
            self.gpu_name = None
            return model.to("cpu")

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
            "gpu_name": self.gpu_name,
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
