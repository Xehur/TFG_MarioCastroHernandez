#!/bin/sh
set -e

echo "[backend] Aplicando migraciones de base de datos (alembic upgrade head)..."
alembic upgrade head

echo "[backend] Iniciando servidor Uvicorn en el puerto 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
