#!/bin/sh
set -e

# Espera a que PostgreSQL acepte conexiones y, si no es posible, explica el
# motivo en una línea en lugar de dejar que alembic falle con una traza larga.
echo "[backend] Comprobando la conexión con la base de datos..."
python - <<'EOF'
import os
import sys
import time

import psycopg2

url = os.environ.get("DATABASE_URL", "")
INTENTOS, ESPERA = 30, 2

for intento in range(1, INTENTOS + 1):
    try:
        psycopg2.connect(url, connect_timeout=3).close()
        print("[backend] Base de datos disponible.")
        sys.exit(0)
    except (psycopg2.OperationalError, UnicodeDecodeError) as exc:
        error = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
        if "password authentication failed" in error:
            print(
                "[backend] ERROR: PostgreSQL rechaza la contraseña (DB_PASSWORD de docker/.env).\n"
                "[backend] La base de datos se creó con otra contraseña, probablemente en una\n"
                "[backend] instalación anterior: PostgreSQL solo la fija la primera vez.\n"
                "[backend] Solución: copia en docker/.env el DB_PASSWORD de la instalación anterior,\n"
                "[backend] o borra la base de datos antigua con 'docker compose down -v'\n"
                "[backend] (se pierden sus datos) y vuelve a arrancar.",
                flush=True,
            )
            time.sleep(15)  # evita reinicios en bucle demasiado rápidos
            sys.exit(1)
        if "could not translate host name" in error:
            motivo = ("no se encuentra el servicio 'db'. Arranca la aplicación con los "
                      "scripts iniciar o con 'docker compose up' (no con 'docker run').")
        else:
            motivo = error
        print(f"[backend] Esperando a la base de datos ({intento}/{INTENTOS}): {motivo}", flush=True)
        time.sleep(ESPERA)

print("[backend] ERROR: no se pudo conectar con la base de datos. Revisa 'docker compose logs db'.",
      flush=True)
sys.exit(1)
EOF

echo "[backend] Aplicando migraciones de base de datos (alembic upgrade head)..."
alembic upgrade head

echo "[backend] Iniciando servidor Uvicorn en el puerto 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
