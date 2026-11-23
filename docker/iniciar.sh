#!/bin/sh
# Prepara y monta la aplicación con Docker eligiendo dónde se ejecuta la IA.
#
# En un equipo nuevo basta con clonar el repositorio y ejecutar este script:
#   1. Crea docker/.env a partir de .env.example con una SECRET_KEY y una
#      DB_PASSWORD aleatorias (si ya existe, solo rellena las que falten).
#   2. Descarga los pesos del modelo (InceptionV3/HE_inceptionv3.pth) del último
#      release de GitHub si no están, y comprueba su SHA-256.
#   3. Pregunta si ejecutar la IA en CPU, GPU NVIDIA o GPU AMD y arranca
#      "docker compose ... up --build -d".
#
# Uso:  sh iniciar.sh                 (pregunta la opción)
#       sh iniciar.sh cpu|nvidia|amd
set -e
cd "$(dirname "$0")"

PESOS_RUTA="../InceptionV3/HE_inceptionv3.pth"
PESOS_SHA256="42515436dd2de4057eba0846aaac2561b38dc88efe960ef6a471807536394a5e"
PESOS_URL_POR_DEFECTO="https://github.com/Xehur/TFG_MarioCastroHernandez/releases/latest/download/HE_inceptionv3.pth"
PLACEHOLDER_DB_PASSWORD="cambia-esta-contrasena"

paso() { printf '==> %s\n' "$1"; }
aviso() { printf 'AVISO: %s\n' "$1" >&2; }

# Cadena aleatoria segura en base64 URL (sin '+', '/' ni '='): válida en URL de BD.
nuevo_secreto() {
    head -c "$1" /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n'
}

sha256_de() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

leer_valor_env() {
    [ -f .env ] || return 0
    grep -E "^[[:space:]]*$1[[:space:]]*=" .env | tail -n 1 | cut -d= -f2- | tr -d '\r"' | sed "s/^'//; s/'\$//; s/^[[:space:]]*//; s/[[:space:]]*\$//"
}

preparar_env() {
    nuevo=0
    if [ ! -f .env ]; then
        paso "Creando docker/.env a partir de .env.example"
        tr -d '\r' < .env.example > .env
        nuevo=1
    else
        # Normaliza finales de línea (un .env editado en Windows puede tener CRLF).
        tr -d '\r' < .env > .env.tmp && mv .env.tmp .env
    fi
    cambios=""
    if grep -Eq '^[[:space:]]*SECRET_KEY[[:space:]]*=[[:space:]]*$' .env; then
        clave=$(nuevo_secreto 48)
        awk -v v="$clave" '{ if ($0 ~ /^[ \t]*SECRET_KEY[ \t]*=[ \t]*$/) print "SECRET_KEY=" v; else print }' .env > .env.tmp && mv .env.tmp .env
        cambios="$cambios SECRET_KEY"
    fi
    if grep -Eq "^[[:space:]]*DB_PASSWORD[[:space:]]*=[[:space:]]*($PLACEHOLDER_DB_PASSWORD)?[[:space:]]*\$" .env; then
        pwd_bd=$(nuevo_secreto 24)
        awk -v v="$pwd_bd" -v ph="$PLACEHOLDER_DB_PASSWORD" '{
            if ($0 ~ "^[ \t]*DB_PASSWORD[ \t]*=[ \t]*(" ph ")?[ \t]*$") print "DB_PASSWORD=" v; else print
        }' .env > .env.tmp && mv .env.tmp .env
        cambios="$cambios DB_PASSWORD"
        if docker volume ls -q --filter name=docker_db_data 2>/dev/null | grep -q .; then
            aviso "Ya existe una base de datos de una instalación anterior (volumen docker_db_data) creada con otra contraseña. PostgreSQL mantendrá la antigua: restaura tu .env anterior o bórrala con 'docker compose down -v' (se pierden los datos)."
        fi
    fi
    if [ -n "$cambios" ]; then
        echo "    Generados valores aleatorios para:$cambios"
    elif [ "$nuevo" -eq 0 ]; then
        echo "    docker/.env ya está configurado."
    fi
}

descargar() {
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$2" "$1"
    else
        echo "no hay curl ni wget instalados" >&2
        return 1
    fi
}

preparar_pesos() {
    if [ -f "$PESOS_RUTA" ]; then
        if [ "$(sha256_de "$PESOS_RUTA")" != "$PESOS_SHA256" ]; then
            aviso "Los pesos existentes no coinciden con el SHA-256 esperado (¿otro modelo?). Se usarán igualmente."
        else
            echo "    Pesos del modelo presentes y verificados."
        fi
        return 0
    fi
    # Prioridad: variable de entorno > docker/.env > último release de GitHub.
    url="${INCEPTION_WEIGHTS_URL:-}"
    [ -n "$url" ] || url=$(leer_valor_env INCEPTION_WEIGHTS_URL)
    [ -n "$url" ] || url="$PESOS_URL_POR_DEFECTO"
    paso "Descargando los pesos del modelo (~98 MB) desde $url"
    temporal="$PESOS_RUTA.part"
    if descargar "$url" "$temporal" && [ "$(sha256_de "$temporal")" = "$PESOS_SHA256" ]; then
        mv "$temporal" "$PESOS_RUTA"
        echo "    Pesos descargados y verificados."
    else
        rm -f "$temporal"
        aviso "No se pudieron descargar o verificar los pesos. La aplicación funcionará sin la IA (responderá 503). Copia HE_inceptionv3.pth en InceptionV3/ o define INCEPTION_WEIGHTS_URL en docker/.env y vuelve a ejecutar el script."
    fi
}

# --- 0. Docker disponible ---------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker no está instalado o no está en el PATH. Instálalo y vuelve a intentarlo." >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "Docker está instalado pero no está en marcha (o tu usuario no tiene permiso para usarlo)." >&2
    exit 1
fi

# --- 1. Configuración y 2. pesos --------------------------------------------
preparar_env
preparar_pesos

# --- 3. CPU o GPU -----------------------------------------------------------
MODO="$1"
if [ -z "$MODO" ]; then
    echo
    echo "¿Dónde quieres ejecutar la IA?"
    echo "  1) CPU (funciona en cualquier equipo)"
    echo "  2) GPU NVIDIA (CUDA)"
    echo "  3) GPU AMD (ROCm)"
    printf "Opción [1]: "
    read -r OPCION
    case "$OPCION" in
        2) MODO=nvidia ;;
        3) MODO=amd ;;
        *) MODO=cpu ;;
    esac
fi

case "$MODO" in
    cpu) ARCHIVOS="-f docker-compose.yml" ;;
    nvidia) ARCHIVOS="-f docker-compose.yml -f docker-compose.gpu-nvidia.yml" ;;
    amd) ARCHIVOS="-f docker-compose.yml -f docker-compose.gpu-amd.yml" ;;
    *) echo "Modo no válido: $MODO (usa cpu, nvidia o amd)" >&2; exit 1 ;;
esac

paso "Montando la aplicación con la IA en: $MODO (la primera vez tarda varios minutos)"
# shellcheck disable=SC2086
docker compose $ARCHIVOS up --build -d

echo
echo "Aplicación:  http://localhost:5173"
echo "Estado IA:   http://localhost:8000/health/ai  (campo \"device\": cpu o cuda)"
echo "Para pararla: docker compose $ARCHIVOS down"
