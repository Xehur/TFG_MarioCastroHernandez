# Entorno Docker

Esta carpeta contiene todo lo necesario para levantar el proyecto completo
(base de datos, backend y frontend) en cualquier ordenador con Docker, sin
instalar Python, Node ni PostgreSQL de forma manual. Al montarlo se elige si la
IA se ejecuta en **CPU**, en una **GPU NVIDIA** o en una **GPU AMD**.

## Requisitos

- Docker Engine y Docker Compose v2 (incluido en Docker Desktop), en marcha.
- Conexion a Internet la primera vez (imagenes base, dependencias y pesos del
  modelo).
- Solo para GPU: ver [Elegir CPU o GPU](#elegir-cpu-o-gpu-para-la-ia).

## Puesta en marcha rapida

En un equipo nuevo basta con clonar el repositorio y ejecutar el script desde
esta carpeta `docker/`:

```bash
git clone https://github.com/Xehur/TFG_MarioCastroHernandez.git
```

```bash
cd TFG_MarioCastroHernandez/docker
```

```bash
.\iniciar.ps1
```

En Linux / macOS el ultimo paso es `sh iniciar.sh`. Si PowerShell bloquea el
script por la politica de ejecucion: `powershell -ExecutionPolicy Bypass -File .\iniciar.ps1`.

El script hace todo lo necesario:

1. **Crea `docker/.env`** a partir de `.env.example` con una `SECRET_KEY` y una
   `DB_PASSWORD` aleatorias y seguras. Si `.env` ya existe, no lo toca salvo para
   rellenar esos dos valores si estan vacios o con el valor de ejemplo.
2. **Descarga los pesos del modelo** (`InceptionV3/HE_inceptionv3.pth`, ~98 MB)
   del ultimo release de GitHub si no estan, y comprueba su SHA-256. Si la
   descarga falla, avisa y continua: la aplicacion funciona sin la IA (responde
   503) hasta que se copien los pesos y se vuelva a ejecutar el script.
3. **Pregunta donde ejecutar la IA** (CPU, GPU NVIDIA o GPU AMD) y arranca
   `docker compose ... up --build -d`.

Tambien acepta la opcion directamente: `.\iniciar.ps1 nvidia`,
`sh iniciar.sh amd`, etc. Volver a ejecutarlo es seguro: reutiliza el `.env` y
los pesos existentes.

La primera vez descargara imagenes base e instalara dependencias (incluido
PyTorch en la variante elegida), por lo que puede tardar varios minutos. Cuando
termine:

- Aplicacion: http://localhost:5173
- Backend (API): http://localhost:8000
- Estado de la IA: http://localhost:8000/health/ai

### Imagenes de ejemplo (dataset BACH)

Para probar la aplicacion sin tener WSI propias, el script `preparar_ejemplos`
descarga WSI del dataset publico **BACH (ICIAR 2018)**
([Kaggle](https://www.kaggle.com/datasets/truthisneverlinear/bach-breast-cancer-histology-images),
licencia CC0) y las importa en tu cuenta, **junto con las regiones anotadas por
patologos** (clases «Benigno», «Carcinoma in situ» y «Carcinoma invasivo»).

Con la aplicacion arrancada y tu cuenta ya creada, desde `docker/`:

```bash
.\preparar_ejemplos.ps1
```

En Linux / macOS: `sh preparar_ejemplos.sh`. Pide el email y la contraseña de tu
cuenta.

- Por defecto importa **2 WSI** (`A03` y `A07`, ~350 MB de descarga). Para otra
  cantidad: `.\preparar_ejemplos.ps1 -Count 4` o `sh preparar_ejemplos.sh --count 4`
  (de 1 a 10; se eligen de menor a mayor tamaño, entre ~170 y ~300 MB cada una).
- Sin las anotaciones: `-SinAnotaciones` / `--sin-anotaciones`.
- No hace falta cuenta de Kaggle ni instalar nada: el script se ejecuta dentro
  del contenedor del backend. Las descargas temporales se borran al terminar.
- Volver a ejecutarlo es seguro: omite las WSI que ya estan en tu cuenta.

Para pararlo (usa los mismos `-f` con los que lo arrancaste):

```bash
docker compose down          # detiene y elimina los contenedores
docker compose down -v       # ademas borra los volumenes (BD e imagenes subidas)
```

## Elegir CPU o GPU para la IA

| Opcion | Comando equivalente | Requisitos del equipo | PyTorch instalado |
|---|---|---|---|
| **CPU** (por defecto) | `docker compose up --build -d` | Ninguno | `+cpu` (imagen ligera) |
| **GPU NVIDIA** | `docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up --build -d` | Driver NVIDIA reciente. **Linux**: NVIDIA Container Toolkit. **Windows**: Docker Desktop con backend WSL2 | `+cu126` (CUDA 12.6) |
| **GPU AMD** | `docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml up --build -d` | **Solo Linux**, con el driver `amdgpu` de ROCm (deben existir `/dev/kfd` y `/dev/dri`) y una GPU compatible con ROCm | `+rocm7.1` |

Como funciona:

- `docker-compose.yml` monta la variante CPU. Los ficheros
  `docker-compose.gpu-*.yml` se **combinan** con el principal y solo cambian el
  servicio `backend`: el indice de PyTorch con el que se construye la imagen
  (`TORCH_INDEX_URL`), la etiqueta de la imagen (`wsi-tfg-backend:cpu`, `:cuda` o
  `:rocm`), `AI_DEVICE` y el acceso del contenedor a la GPU.
- PyTorch expone las GPU NVIDIA (CUDA) y AMD (ROCm) con el mismo dispositivo
  `cuda`, asi que el codigo de la IA es el mismo en ambos casos.
- **Si la GPU no esta disponible o falla, la IA sigue funcionando en CPU** y lo
  indica en el log del backend. Nunca impide arrancar la aplicacion.

Comprobar que se esta usando la GPU:

- `http://localhost:8000/health/ai` devuelve `device` (`cpu` o `cuda`), `build`
  (`cpu`, `cuda 12.6` o `rocm 7.1`), `gpu_available` y `gpu_name`.
- En el visor, el panel de Clasificacion IA muestra una etiqueta **CPU** o **GPU**
  junto al nombre del modelo (pasando el raton aparece el nombre de la GPU).
- En el log del backend (`docker compose logs backend`) aparece
  `AI_DEVICE=cuda -> cuda [nombre de la GPU]` al cargar el modelo.

Notas sobre GPU:

- **AMD en Windows**: Docker Desktop no expone las GPU AMD a los contenedores
  Linux, asi que en Windows con una GPU AMD hay que usar la variante CPU.
- **GPU AMD no listada oficialmente por ROCm** (algunas RX 7000 de gama media): si
  `/health/ai` muestra `device: cpu` con la variante AMD, descomenta
  `HSA_OVERRIDE_GFX_VERSION: "11.0.0"` en `docker-compose.gpu-amd.yml`.
- **Otra version de CUDA/ROCm**: define `TORCH_CUDA_INDEX_URL` (p. ej.
  `.../whl/cu129`) o `TORCH_ROCM_INDEX_URL` (p. ej. `.../whl/rocm7.2`) en `.env`.
- Las imagenes GPU son mucho mas grandes que la CPU (varios GB) porque incluyen
  las librerias de CUDA o ROCm.

## Que hace cada servicio

| Servicio  | Imagen / build            | Puerto host | Descripcion |
|-----------|---------------------------|-------------|-------------|
| `db`      | postgres:16-alpine        | interno     | Base de datos PostgreSQL con volumen persistente. |
| `backend` | `backend.Dockerfile`      | 8000        | FastAPI + OpenSlide + PyTorch. Aplica las migraciones de Alembic al arrancar y sirve la API. |
| `frontend`| `frontend.Dockerfile`     | 5173        | Build de Vite servido por Nginx (SPA de React). |

## Archivos

- `docker-compose.yml` — orquesta los tres servicios y sus volumenes (IA en CPU).
- `docker-compose.gpu-nvidia.yml` / `docker-compose.gpu-amd.yml` — variantes de
  la IA en GPU que se combinan con el anterior.
- `iniciar.ps1` / `iniciar.sh` — preparan `.env` y los pesos del modelo y montan
  la aplicacion preguntando CPU o GPU.
- `preparar_ejemplos.ps1` / `preparar_ejemplos.sh` — descargan WSI de ejemplo del
  dataset BACH con sus anotaciones y las importan en tu cuenta.
- `backend.Dockerfile` — imagen del backend (dependencias de sistema para
  OpenSlide, PyTorch de la variante elegida, `requirements.txt`, entrypoint).
- `backend-entrypoint.sh` — ejecuta `alembic upgrade head` y luego `uvicorn`.
- `frontend.Dockerfile` — build multi-etapa (Node para compilar, Nginx para servir).
- `nginx.conf` — configuracion de Nginx con fallback de SPA.
- `.env.example` — plantilla de variables de entorno.

## Configuracion (variables de entorno)

Se definen en el archivo `.env` de esta carpeta (ver `.env.example`):

- `DB_USER`, `DB_PASSWORD`, `DB_NAME`: credenciales de PostgreSQL.
  `DB_PASSWORD` es obligatoria y no puede ser trivial (`1234`, `postgres`...).
- `SECRET_KEY`: clave para firmar los tokens JWT. Obligatoria, minimo 32
  caracteres aleatorios: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `CORS_ORIGINS`: origenes del frontend en JSON (por defecto
  `["http://localhost:5173"]`). Debe coincidir con la URL desde la que se abre
  la aplicacion.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: validez del token (por defecto 1440 = 24 h).
- `VITE_API_BASE_URL`: URL del backend tal como la ve el NAVEGADOR del usuario.
  Por defecto `http://localhost:8000`. Si sirves la app desde otra maquina,
  ponla a `http://IP_DEL_SERVIDOR:8000` y reconstruye el frontend
  (`docker compose up --build frontend`), ya que Vite la embebe en el build.
- `ENABLE_DOCS`: `true` para activar la documentacion interactiva en `/docs`
  (desactivada por defecto en Docker).
- IA (opcionales): `AI_DEVICE` (`cpu` o `auto` en la variante CPU),
  `AI_BATCH_SIZE` (campos por lote; 32 por defecto en GPU),
  `TORCH_CUDA_INDEX_URL` y `TORCH_ROCM_INDEX_URL` (version de CUDA/ROCm).

## Notas

- **Persistencia**: las imagenes WSI subidas y los overlays de analisis se
  guardan en el volumen `uploads_data`; la base de datos en `db_data`. Sobreviven
  a `docker compose down` (no a `down -v`) y al cambiar entre CPU y GPU.
- **Migraciones**: las tablas se crean automaticamente en el primer arranque del
  backend mediante Alembic. No hace falta ningun paso manual.
- **Modelo de IA**: el clasificador InceptionV3 lee sus pesos de
  `InceptionV3/HE_inceptionv3.pth`, montado en el contenedor como `/models` en
  solo lectura. No se versionan en Git (97,8 MB): se publican como fichero
  adjunto de cada release de GitHub y los scripts `iniciar` los descargan de
  `https://github.com/Xehur/TFG_MarioCastroHernandez/releases/latest/download/HE_inceptionv3.pth`.
  Para usar otra ubicacion, define `INCEPTION_WEIGHTS_URL` en `.env` (o como
  variable de entorno). Para que la descarga funcione, el repositorio debe ser
  publico y el release debe llevar adjunto `HE_inceptionv3.pth`.
- **Si borras `.env` con una base de datos ya creada**: el script genera una
  contraseña nueva, pero PostgreSQL conserva la del primer arranque (el script
  avisa). Restaura el `.env` anterior o borra los datos con `docker compose down -v`.
- **CORS**: el contenedor arranca en modo produccion, que solo admite los
  origenes de `CORS_ORIGINS`. Si sirves el frontend desde otra IP o dominio,
  añadelo ahi.
- **Seguridad**: si falta `SECRET_KEY` o `DB_PASSWORD`, `docker compose` se
  niega a arrancar; si son inseguras, el backend se detiene con un error que
  indica que corregir.
