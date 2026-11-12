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

# Instala dependencias primero para aprovechar la caché de capas.
# PyTorch se instala desde el índice CPU: en Linux, el paquete por defecto de
# PyPI incluye CUDA y sus librerías NVIDIA (varios GB) que el contenedor no usa
# (la inferencia es en CPU). Las versiones siguen fijadas en requirements.txt.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Copia el código del backend (el contexto de build es la raíz del repo)
COPY backend/ ./

# Script de arranque: aplica migraciones y lanza uvicorn
COPY docker/backend-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
