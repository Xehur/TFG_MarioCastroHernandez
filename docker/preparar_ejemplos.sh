#!/bin/sh
# Descarga WSI de ejemplo del dataset BACH y las importa en tu cuenta.
#
# Ejecuta backend/scripts/preparar_ejemplos_bach.py dentro del contenedor del
# backend (no hace falta instalar Python). La aplicación debe estar arrancada
# (iniciar.sh) y debes haber creado ya tu cuenta: se pedirán su email y
# contraseña.
#
# Uso:  sh preparar_ejemplos.sh                 (2 WSI, ~350 MB)
#       sh preparar_ejemplos.sh --count 4       (de 1 a 10)
#       sh preparar_ejemplos.sh --sin-anotaciones
set -e
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker no está instalado o no está en el PATH." >&2
    exit 1
fi

if ! docker compose exec backend python scripts/preparar_ejemplos_bach.py "$@"; then
    echo
    echo "Si el error indica que el servicio \"backend\" no está en marcha, arranca antes la aplicación con: sh iniciar.sh" >&2
    exit 1
fi
