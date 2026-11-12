# Entorno Docker

Esta carpeta contiene todo lo necesario para levantar el proyecto completo
(base de datos, backend y frontend) en cualquier ordenador con Docker, sin
instalar Python, Node ni PostgreSQL de forma manual.

## Requisitos

- Docker Engine y Docker Compose v2 (incluido en Docker Desktop).

## Puesta en marcha rapida

Desde esta carpeta `docker/`:

```bash
# 1. (Opcional) crea tu archivo de configuracion a partir del ejemplo
cp .env.example .env      # en Windows PowerShell: Copy-Item .env.example .env

# 2. Construye y arranca los tres servicios
docker compose up --build
```

La primera vez descargara imagenes base e instalara dependencias (incluido
PyTorch en su version solo CPU, sin las librerias CUDA), por lo que puede tardar
varios minutos. Cuando termine:

- Frontend: http://localhost:5173
- Backend (API):  http://localhost:8000
- Documentacion interactiva de la API: http://localhost:8000/docs

Para pararlo:

```bash
docker compose down          # detiene y elimina los contenedores
docker compose down -v       # ademas borra los volumenes (BD e imagenes subidas)
```

## Que hace cada servicio

| Servicio  | Imagen / build            | Puerto host | Descripcion |
|-----------|---------------------------|-------------|-------------|
| `db`      | postgres:16-alpine        | interno     | Base de datos PostgreSQL con volumen persistente. |
| `backend` | `backend.Dockerfile`      | 8000        | FastAPI + OpenSlide + PyTorch. Aplica las migraciones de Alembic al arrancar y sirve la API. |
| `frontend`| `frontend.Dockerfile`     | 5173        | Build de Vite servido por Nginx (SPA de React). |

## Archivos

- `docker-compose.yml` — orquesta los tres servicios y sus volumenes.
- `backend.Dockerfile` — imagen del backend (dependencias de sistema para
  OpenSlide, instalacion de `requirements.txt`, entrypoint).
- `backend-entrypoint.sh` — ejecuta `alembic upgrade head` y luego `uvicorn`.
- `frontend.Dockerfile` — build multi-etapa (Node para compilar, Nginx para servir).
- `nginx.conf` — configuracion de Nginx con fallback de SPA.
- `.env.example` — plantilla de variables de entorno.

## Configuracion (variables de entorno)

Se definen en el archivo `.env` de esta carpeta (ver `.env.example`):

- `DB_USER`, `DB_PASSWORD`, `DB_NAME`: credenciales de PostgreSQL.
- `SECRET_KEY`: clave para firmar los tokens JWT (cambiala en produccion).
- `ACCESS_TOKEN_EXPIRE_MINUTES`: validez del token (por defecto 1440 = 24 h).
- `VITE_API_BASE_URL`: URL del backend tal como la ve el NAVEGADOR del usuario.
  Por defecto `http://localhost:8000`. Si sirves la app desde otra maquina,
  ponla a `http://IP_DEL_SERVIDOR:8000` y reconstruye el frontend
  (`docker compose up --build frontend`), ya que Vite la embebe en el build.

## Notas

- **Persistencia**: las imagenes WSI subidas y los overlays de analisis se
  guardan en el volumen `uploads_data`; la base de datos en `db_data`. Sobreviven
  a `docker compose down` (no a `down -v`).
- **Migraciones**: las tablas se crean automaticamente en el primer arranque del
  backend mediante Alembic. No hace falta ningun paso manual.
- **Modelo de IA**: el clasificador InceptionV3 lee sus pesos de
  `InceptionV3/HE_inceptionv3.pth` (en la raiz del repo), montado en el
  contenedor como `/models` en solo lectura. Los pesos no se versionan en Git:
  copia el fichero a esa ruta antes de arrancar. Si falta, los endpoints de IA
  responden 503 y el resto de la aplicacion funciona con normalidad.
- **CORS**: el backend permite cualquier origen por defecto, por lo que el
  frontend puede llamarlo sin configuracion adicional.
