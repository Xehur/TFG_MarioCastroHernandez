# Imagen del backend: FastAPI + OpenSlide + PyTorch
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias de sistema:
# - libglib2.0-0: requerido por OpenSlide (openslide-bin)
# - libgomp1: OpenMP, usado por numpy/scipy/scikit-image/torch
# - curl: para el healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Variante de PyTorch según el hardware de la IA (la elige docker-compose):
#   CPU (por defecto)  https://download.pytorch.org/whl/cpu      (imagen ligera)
#   GPU NVIDIA         https://download.pytorch.org/whl/cu126    (CUDA 12.6)
#   GPU AMD            https://download.pytorch.org/whl/rocm7.1  (ROCm 7.1)
# Las versiones de torch/torchvision siguen fijadas en requirements.txt; el índice
# extra solo decide qué compilación se instala (+cpu, +cu126 o +rocm7.1).
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# Instala dependencias primero para aprovechar la caché de capas.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install --extra-index-url ${TORCH_INDEX_URL} -r requirements.txt \
    && python -c "import torch; print('PyTorch', torch.__version__)"

# Copia el código del backend (el contexto de build es la raíz del repo)
COPY backend/ ./

# Script de arranque: aplica migraciones y lanza uvicorn
COPY docker/backend-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
