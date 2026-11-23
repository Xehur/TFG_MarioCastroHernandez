
# Visor WSI con análisis de tejido e IA (histopatología mamaria)

Aplicación web para **visualizar imágenes de portaobjetos completos (WSI)**,
**anotarlas** y **analizar su tejido** con visión por computador clásica y con un
**modelo de IA (InceptionV3)** que clasifica tejido mamario en *Normal*, *Benigno*,
*Carcinoma in situ* y *Carcinoma invasivo*.

> **Uso académico / de investigación (TFG).** Las predicciones no constituyen un
> diagnóstico clínico, las confianzas del modelo no están calibradas y el modelo no
> se ha validado sobre WSI completas de pacientes.

> **¿Buscas cómo usar la aplicación?** Consulta el
> [Manual de usuario](Manual_Usuario.md), con capturas de cada pantalla. Este
> README describe cómo funciona por dentro y cómo instalarla.

---

## Índice

1. [Qué hace la aplicación](#1-qué-hace-la-aplicación)
2. [Arquitectura](#2-arquitectura)
3. [Tecnologías](#3-tecnologías)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Backend por dentro](#5-backend-por-dentro)
6. [Análisis clásico del tejido](#6-análisis-clásico-del-tejido)
7. [Clasificación de tejido con IA (InceptionV3)](#7-clasificación-de-tejido-con-ia-inceptionv3)
8. [Anotaciones e interoperabilidad COCO](#8-anotaciones-e-interoperabilidad-coco)
9. [Paleta de comandos](#9-paleta-de-comandos)
10. [Dashboard de análisis](#10-dashboard-de-análisis)
11. [Frontend por dentro](#11-frontend-por-dentro)
12. [Catálogo de la API](#12-catálogo-de-la-api)
13. [Cachés, versionado y almacenamiento](#13-cachés-versionado-y-almacenamiento)
14. [Pruebas](#14-pruebas)
15. [Puesta en marcha](#15-puesta-en-marcha)
16. [Limitaciones y trabajo futuro](#16-limitaciones-y-trabajo-futuro)
17. [Glosario](#17-glosario)

---

## 1. Qué hace la aplicación

Una WSI es la digitalización completa de un portaobjetos: decenas de miles de
píxeles por lado (p. ej. 156 000 × 64 000 px, varios GB). La aplicación está
diseñada para **no cargar nunca la imagen completa en memoria**: trabaja con la
pirámide de resoluciones de la WSI, con miniaturas y con lectura de regiones bajo
demanda.

| Funcionalidad | Qué permite | Dónde vive |
|---|---|---|
| Cuentas de usuario | Registro, login con JWT, edición de nombre/email/contraseña | `routers/auth.py`, `pages/Login`, `pages/Settings` |
| Gestión de imágenes | Subir una o varias WSI (arrastrar y soltar), listar y borrar las propias | `routers/images.py`, `pages/ImageList`, `pages/Upload` |
| Visor Deep Zoom | Zoom y desplazamiento fluidos a resolución completa | `WSIViewer.jsx` + endpoints DZI |
| Anotaciones | Rectángulos, círculos y polígonos con clases configurables | `routers/annotations.py`, `components/wsi/annotations/` |
| Detección de tejido | Máscara tejido/fondo (sin IA) superpuesta al visor | `tissue_detection.py`, `TissueMaskControl.jsx` |
| Mapa de densidad | Heatmap de la fracción de tejido por celdas | `density_generation.py`, `DensityMapViewer.jsx` |
| Clasificación IA | Mapa de clases de tejido mamario + estadísticas | `inception_classifier.py`, `ai_classification_service.py`, `AIClassificationControl.jsx` |
| Análisis por región | Todos los análisis anteriores restringidos a una anotación | `annotation_analysis_service.py` |
| Importar/exportar COCO | Intercambio de anotaciones con otras herramientas | `coco_service.py`, `CocoImportModal.jsx` |
| Paleta de comandos | Todas las acciones con `Ctrl+K` | `command_registry.py`, `CommandPalette.jsx` |
| Dashboard | Métricas legibles (mm², % carcinoma, densidad, fragmentos…) | `analytics_service.py`, `AnalyticsDashboard.jsx` |

**Flujo típico de uso**

1. El usuario se registra o inicia sesión.
2. Sube una o varias WSI (`.svs`, `.tif`, `.tiff`, `.mrxs`). El backend las guarda
   en `uploads/<id_usuario>/` y extrae sus metadatos con OpenSlide.
3. Abre una imagen: OpenSeadragon pide solo los *tiles* visibles al nivel de zoom
   actual.
4. Activa la máscara de tejido, el mapa de densidad o la clasificación IA; cada
   resultado se dibuja como una capa semitransparente sobre la imagen y se cachea.
5. Dibuja anotaciones, las clasifica y puede analizar cada región por separado.
6. Consulta el dashboard o exporta las anotaciones a COCO.

---

## 2. Arquitectura

```
┌───────────────────────────────┐   HTTP/JSON, PNG y JPEG   ┌──────────────────────────────────┐
│ FRONTEND (SPA)                │ ◄───────────────────────► │ BACKEND (FastAPI)                │
│ React 19 + Vite               │   Authorization: Bearer   │ routers/   → validación y HTTP   │
│ OpenSeadragon (visor WSI)     │                           │ services/  → lógica de negocio   │
│ Axios (cliente API)           │                           │   wsi/      OpenSlide + cachés   │
│ Recharts (gráficas)           │                           │   analysis/ tejido, densidad, IA │
└───────────────────────────────┘                           │ models/    → ORM SQLAlchemy      │
                                                            └────────┬──────────────┬──────────┘
                                                                     │              │
                                               ┌─────────────────────▼───┐   ┌──────▼─────────────────────┐
                                               │ PostgreSQL              │   │ Sistema de ficheros        │
                                               │ usuarios, imágenes,     │   │ uploads/<user>/   WSI      │
                                               │ anotaciones, resultados │   │ uploads/analysis/ PNG      │
                                               │ (JSON)                  │   │ InceptionV3/*.pth (pesos)  │
                                               └─────────────────────────┘   └────────────────────────────┘
```

Principios de diseño:

- **Routers finos, servicios con la lógica.** Los routers validan la entrada,
  comprueban permisos, delegan en `services/` y traducen excepciones a códigos HTTP.
- **Fachada sobre OpenSlide.** Todo acceso a la WSI pasa por `OpenSlideService`
  (`services/wsi/openslide_service.py`), lo que aísla la librería nativa y permite
  sustituirla por objetos falsos en los tests.
- **Interfaces sustituibles.** `TissueDetector` y `DensityGenerator` definen una
  interfaz con una implementación por defecto; los endpoints solo usan
  `detect_tissue()` / `generate_density_map()`.
- **Binarios fuera de la BD.** PostgreSQL guarda solo datos pequeños (metadatos,
  coordenadas, resultados en JSON); las WSI y los PNG de los overlays van a disco.
- **Todo se calcula una vez.** Cada análisis se cachea (PNG en disco + JSON en BD)
  y se versiona para regenerarse solo cuando cambia el algoritmo o el modelo.

**Recorrido de una petición** (p. ej. `GET /images/7/ai-classification`):

1. Axios añade la cabecera `Authorization: Bearer <JWT>` (interceptor de `api.js`).
2. FastAPI resuelve `get_current_user` (`core/deps.py`): decodifica el JWT y carga el
   usuario; sin token válido responde 401.
3. El router comprueba que la imagen existe y que el fichero está en disco.
4. `ai_classification_service.get_or_create_image_classification` devuelve el
   resultado cacheado si sigue siendo válido o lo genera.
5. El router responde el PNG del overlay con `Cache-Control: no-store`.
6. El frontend lo convierte en un *object URL* y lo añade al visor con
   `viewer.addSimpleImage`, alineado con la imagen base.

---

## 3. Tecnologías

### Backend (Python 3.12)

| Tecnología | Uso |
|---|---|
| FastAPI 0.104 + Uvicorn | API REST y servidor ASGI |
| Pydantic 2 / pydantic-settings | Esquemas de entrada/salida y configuración por `.env` |
| SQLAlchemy 2.0 + Alembic | ORM y migraciones de la base de datos |
| PostgreSQL (psycopg2) | Base de datos relacional (SQLite en los tests) |
| OpenSlide (openslide-python + openslide-bin) | Lectura de WSI, pirámides y Deep Zoom |
| NumPy, SciPy, scikit-image | Visión por computador clásica (OD, Otsu, morfología, etiquetado) |
| Matplotlib | Colormaps de los mapas de densidad |
| PyTorch 2.12 + torchvision 0.27 | Arquitectura InceptionV3 e inferencia del modelo |
| Pillow | Lectura/escritura de imágenes y PNG |
| passlib + bcrypt, python-jose | Hash de contraseñas y tokens JWT (HS256) |
| pytest, httpx | Pruebas |

### Frontend

| Tecnología | Uso |
|---|---|
| React 19 + Vite | SPA y servidor de desarrollo |
| React Router 7 | Rutas y rutas protegidas |
| OpenSeadragon 6 | Visor Deep Zoom y capas superpuestas |
| Axios | Cliente HTTP con interceptores |
| Recharts | Gráficas del dashboard (exportables a PNG/SVG) |
| lucide-react | Iconos |
| Vitest + Testing Library | Pruebas de componentes y servicios |

---

## 4. Estructura del repositorio

```
Projecto_TFG/
├── backend/
│   ├── app/
│   │   ├── main.py               # Crea la app FastAPI: CORS, middleware y routers
│   │   ├── config.py             # Settings (variables de entorno / .env)
│   │   ├── db.py                 # Motor SQLAlchemy y Base declarativa
│   │   ├── logging_config.py     # Logs a consola y a fichero rotativo (logs/)
│   │   ├── middleware.py         # Cabecera X-Process-Time + log de cada petición
│   │   ├── core/
│   │   │   ├── deps.py           # get_db() y get_current_user() (JWT)
│   │   │   └── security.py       # bcrypt y creación/validación de JWT
│   │   ├── models/               # Tablas: user, image, annotation, analysis
│   │   ├── schemas/              # Modelos Pydantic de petición/respuesta
│   │   ├── routers/              # Endpoints: auth, users, images, annotations,
│   │   │                         #   coco, analysis, commands, health
│   │   └── services/
│   │       ├── wsi/
│   │       │   ├── openslide_service.py   # Fachada OpenSlide (miniaturas, regiones, campos)
│   │       │   └── slide_cache.py         # LRU de slides abiertos y de tiles JPEG
│   │       ├── analysis/
│   │       │   ├── tissue_detection.py    # Detector de tejido (OD + histéresis)
│   │       │   ├── tissue_service.py      # Orquesta y cachea la máscara de tejido
│   │       │   ├── density_generation.py  # Cálculo y coloreado del mapa de densidad
│   │       │   ├── density_service.py     # Orquesta y cachea el mapa de densidad
│   │       │   ├── analysis_service.py    # Análisis consolidado (tejido + densidad)
│   │       │   ├── inception_classifier.py      # Carga e inferencia de InceptionV3
│   │       │   ├── ai_classification_service.py # Rejilla, muestreo, overlay y caché de la IA
│   │       │   ├── annotation_analysis_service.py # Todo lo anterior acotado a una anotación
│   │       │   └── analytics_service.py   # Datos del dashboard
│   │       ├── commands/          # Catálogo y ejecutor de la paleta de comandos
│   │       └── coco_service.py    # Conversión anotaciones <-> COCO
│   ├── alembic/versions/          # Migraciones de la base de datos
│   ├── scripts/smoke_inception.py # Prueba en CPU del checkpoint de la IA
│   ├── tests/                     # Pruebas pytest
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx                # Rutas de la SPA
│       ├── context/               # AuthProvider / useAuth (sesión)
│       ├── services/              # Un cliente por dominio de la API (api.js = Axios)
│       ├── pages/                 # Login, Register, ImageList, Upload, Settings, ImageViewer
│       ├── components/
│       │   ├── auth/              # ProtectedRoute, UserMenu
│       │   ├── upload/            # ImageDropZone
│       │   └── wsi/               # WSIViewer, ZoomControls, ViewerInfoBar
│       │       ├── annotations/   # Capa SVG, barra de herramientas, panel, modales
│       │       └── analysis/      # Controles de tejido/densidad/IA, dashboard, paleta
│       └── utils/                 # Errores de API, helpers, monitor de rendimiento
├── InceptionV3/                   # Material del modelo de IA
│   ├── HE_inceptionv3.pth         # Pesos (NO versionado; ruta configurable)
│   ├── src/finetune.py            # Script de entrenamiento (referencia)
│   ├── src/inference.py           # Script de inferencia original (referencia)
│   ├── metricas.txt, matriz_confusion.png, graficas_rendimiento.png
│   └── environment.yml            # Entorno con el que se entrenó
├── docker/                        # Dockerfiles, docker-compose, scripts iniciar y su README
├── docs/manual/img/               # Capturas del manual de usuario
├── Manual_Usuario.md              # Manual de usuario (qué hacer en cada pantalla)
└── README.md
```

`pytorch-CycleGAN-and-pix2pix/` (si está presente en tu copia) contiene generadores
de **transformación de tinción** H&E → HER2/Ki67. No son clasificadores y la
aplicación **no los usa**.

---

## 5. Backend por dentro

### 5.1 Arranque y configuración

`app/main.py` crea la aplicación, registra CORS, el middleware de tiempos
(`X-Process-Time` + una línea de log por petición) y los ocho routers. La
configuración vive en `app/config.py` (`Settings`, pydantic-settings) y se puede
sobrescribir con variables de entorno o un fichero `.env`:

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:1234@localhost:5432/wsi_db` | Conexión a PostgreSQL |
| `ENVIRONMENT` | `development` | Con `production` se exige configuración segura (ver abajo) |
| `SECRET_KEY`, `ALGORITHM` | valor de desarrollo, `HS256` | Firma de los JWT |
| `CORS_ORIGINS` | `["*"]` | Orígenes permitidos (JSON). En producción no se admite `*` |
| `ENABLE_DOCS` | activo salvo en producción | Expone `/docs`, `/redoc` y `/openapi.json` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 (24 h) | Caducidad del token |
| `UPLOAD_DIR` | `uploads` | Carpeta de WSI y resultados |
| `MAX_FILE_SIZE`, `CHUNK_SIZE` | 10 GB, 8 MB | Límite de subida y tamaño de bloque |
| `INCEPTION_WEIGHTS_PATH` | `<repo>/InceptionV3/HE_inceptionv3.pth` | Pesos del modelo |
| `INCEPTION_WEIGHTS_SHA256` | hash del checkpoint actual | Verificación de integridad (aviso si no coincide) |
| `AI_DEVICE` | `cpu` | Dispositivo de inferencia: `cpu`, `cuda`/`gpu` (NVIDIA CUDA o AMD ROCm) o `auto`. Si se pide GPU y no hay, usa CPU |
| `AI_FIELD_MPP`, `AI_FIELD_WIDTH_PX`, `AI_FIELD_HEIGHT_PX` | 0.42, 2048, 1536 | Campo físico que ve el modelo (≈ 860 × 645 µm) |

Con `ENVIRONMENT=production` el backend **no arranca** si `SECRET_KEY` es la de
desarrollo o tiene menos de 32 caracteres, si `DATABASE_URL` usa una contraseña
trivial (`1234`, `postgres`...) o si `CORS_ORIGINS` contiene `*`.
| `AI_MAX_PATCHES` | 1000 | Máximo de campos con tejido clasificados por análisis |
| `AI_MIN_TISSUE_FRAC` | 0.35 | Fracción mínima de tejido para analizar una celda |
| `AI_BATCH_SIZE`, `AI_READ_WORKERS` | 16, 4 | Tamaño de lote e hilos de lectura de la WSI |

### 5.2 Autenticación y permisos

- **Registro / login** (`routers/auth.py`): las contraseñas se guardan con
  **bcrypt** (`core/security.py`) y nunca se devuelven. El login devuelve un **JWT**
  (`sub` = id de usuario, `exp` = caducidad) firmado con HS256.
- **Protección de endpoints**: todos los endpoints de negocio dependen de
  `get_current_user` (`core/deps.py`), que lee el token `Bearer`, lo valida y carga
  el usuario. Sin token o con token inválido: **401**; usuario inactivo: **403**.
- **Propiedad**: cada imagen pertenece a un usuario. El listado solo devuelve las
  propias y borrar una ajena devuelve **403**.
- **Cuenta**: `PATCH /auth/me` cambia nombre, email (comprobando que no esté en
  uso) y contraseña (exige la actual).
- **En el navegador**: el token y el usuario se guardan en `localStorage`; al
  recargar, `AuthProvider` revalida la sesión con `GET /auth/me`. Un 401 en
  cualquier petición cierra la sesión (interceptor de `api.js`).

### 5.3 Modelo de datos

| Tabla | Campos principales | Notas |
|---|---|---|
| `users` | `email` (único), `full_name`, `hashed_password`, `is_active` | |
| `images` | `filename`, `file_path`, `user_id`, `width`, `height`, `level_count`, `downsamples`, `properties` (JSON), `file_size_mb` | **Única por (`user_id`, `filename`)**: dos usuarios pueden subir el mismo nombre |
| `annotations` | `image_id`, `user_id`, `shape_type`, `coordinates` (JSON, px de nivel 0), `label`, `color`, `class_id` | `shape_type`: `rectangle` · `circle` · `polygon` |
| `annotation_classes` | `name`, `color`, `description`, `user_id` | Clases configurables (p. ej. "Tumor") |
| `analysis_results` | `image_id`, `annotation_id` (nullable), `analysis_type`, `result_data` (JSON) | `tissue_mask`, `ai_classification`, `full_analysis`… |
| `density_maps` | `image_id`, `annotation_id` (nullable), `grid_size`, `density_data` (JSON) | Matriz de densidades y metadatos |

`annotation_id = NULL` significa "análisis de la imagen completa". Las columnas
JSON permiten añadir campos a los resultados sin migrar el esquema. Las migraciones
están en `backend/alembic/versions/` (la última, `d4e5f6a7b8c9`, cambia la unicidad
del nombre de imagen a "por usuario").

`properties` guarda los metadatos de OpenSlide, entre ellos **`openslide.mpp-x`**
(µm por píxel), que se usa para todas las medidas físicas (escala de la IA,
superficies en mm²).

### 5.4 Gestión de imágenes

- **Subida** (`POST /images/upload` y `/images/upload-multiple`): se valida la
  extensión, se comprueba que **ese usuario** no tenga ya un archivo con ese nombre
  (409) y se guarda en `uploads/<user_id>/<nombre>` **por bloques de 8 MB**, sin
  cargarlo entero en memoria. Después se abre con OpenSlide para extraer
  dimensiones, niveles y propiedades; si no es una WSI válida se borra y se
  responde 422. La subida múltiple devuelve un resultado por fichero (207).
- **Borrado** (`DELETE /images/{id}`): saca primero el slide de la caché (en
  Windows no se puede borrar un fichero que OpenSlide mantiene abierto), elimina el
  fichero, la carpeta de resultados `uploads/analysis/<id>/` y el registro (los
  análisis se borran en cascada).

### 5.5 Visualización Deep Zoom

El visor usa el estándar **DZI (Deep Zoom Image)**:

1. `GET /images/{id}/dzi.dzi` devuelve el XML que describe la pirámide (tamaño,
   niveles, tile de 256 px con 1 px de solape). Lo genera el propio
   `DeepZoomGenerator` de OpenSlide, para que coincida exactamente con los tiles.
2. `GET /images/{id}/dzi_files/{nivel}/{col}_{fila}.jpeg` devuelve cada tile.
   `DeepZoomGenerator` elige el nivel de la pirámide óptimo y reescala si hace falta.
3. `slide_cache.py` mantiene dos cachés LRU *thread-safe*: hasta **8 slides
   abiertos** (abrir una WSI es caro) y **2048 tiles JPEG** ya renderizados
   (cabecera `X-Tile-Cache: HIT`). Los tiles se sirven con `max-age=86400`.
4. Como los tiles exigen autenticación, OpenSeadragon se configura con
   `loadTilesWithAjax: true` y `ajaxHeaders` con el JWT.

### 5.6 Acceso a la WSI (`OpenSlideService`)

| Método | Qué hace | Lo usan |
|---|---|---|
| `get_thumbnail_rgb(max_size=2048)` | Miniatura de la imagen completa + escala | Tejido, densidad, IA (imagen) |
| `read_region_rgb(x, y, w, h, max_size)` | Región de nivel 0 leída del nivel de pirámide adecuado | Análisis por anotación |
| `read_field_rgb(cx, cy, w0, h0, out_w, out_h)` | Campo rectangular de tamaño físico fijo, centrado y acotado a la imagen | IA |
| `read_patch_rgb(...)` | Variante cuadrada de lo anterior | — |
| `get_mpp_x()` | µm/px de nivel 0 (o `None`) | IA, dashboard |

`read_field_rgb` elige el nivel más detallado cuyo *downsample* no reduzca el campo
por debajo del tamaño de salida: lee lo justo y conserva la escala física.

---

## 6. Análisis clásico del tejido

Los tres análisis clásicos trabajan sobre una **miniatura** de como mucho 2048 px de
lado (o sobre la región de una anotación) y producen un PNG RGBA que el frontend
superpone a la imagen.

### 6.1 Detección de tejido (`tissue_detection.py`)

Objetivo: separar el **tejido teñido** del **cristal** del portaobjetos. Se hace sin
IA, con `ClassicalTissueDetector`, en estos pasos:

1. **Densidad óptica (OD) respecto al cristal.** Se estima el color del cristal como
   el percentil 99 de cada canal (con un mínimo de 0,85 para regiones casi sin
   cristal) y se calcula `OD = -log10(I / I_cristal)` por canal, quedándose con el
   **máximo de los tres canales**. El cristal tiene OD ≈ 0; cualquier tinción, por
   pálida que sea, OD > 0. Usar el máximo es clave: el rosa muy pálido solo absorbe
   en un canal.
2. **Tinta de rotulador.** Los píxeles con tono amarillo-verde-cian (fuera de la gama
   H&E), saturación > 0,12 y OD > 0,08 se marcan como tinta y se dilatan 2 px.
3. **Umbral con histéresis.**
   - *Fuerte*: Otsu sobre la OD, recortada al percentil 99,5 para que unos pocos
     píxeles extremos (polvo, restos de tinta) no desplacen el umbral.
   - *Débil*: justo por encima del ruido del cristal:
     `max(mediana + 6·1,4826·MAD, 0,035)` (sin superar el fuerte), o bien
     saturación > 0,08.
   - Se conservan solo las regiones débiles **conectadas** a alguna región fuerte.
     Así se recupera el tejido pálido (grasa, estroma laxo, eosina clara) sin aceptar
     manchas aisladas del cristal.
4. **Franjas del escáner.** Si las filas/columnas pegadas a un borde están cubiertas
   en más de un 60 %, son finas (≤ 5 % del lado) y justo después la cobertura cae a
   menos de la mitad, se eliminan. Dentro de la franja solo se conserva el tejido
   que continúa por debajo (la punta de un cilindro que entra en ella).
5. **Componentes de tinta.** Se descartan las regiones cuyo color es en más de un
   30 % de tinta (también las zonas pálidas de un trazo de rotulador).
6. **Limpieza morfológica.** Cierre (radio 3), relleno de huecos interiores de hasta
   el 0,2 % del área (vacuolas de grasa) y eliminación de objetos de menos del
   0,02 % del área.

El resultado incluye la máscara, el **% de tejido**, los umbrales de OD, el color
del cristal, el % de tinta excluida, el **nº de fragmentos** (regiones conexas) y
sus áreas. Con la miniatura de 2048 px tarda menos de 1 s. La máscara se convierte
en un overlay verde semitransparente (`mask_to_rgba_overlay`).

### 6.2 Mapa de densidad (`density_generation.py`, `density_service.py`)

1. La imagen se divide en celdas cuadradas de `grid_size` px **de nivel 0** (128,
   256, 512 o 1024; por defecto 256).
2. Para cada celda, **densidad = fracción de píxeles de tejido** en [0, 1].
3. La matriz se colorea con un colormap de Matplotlib (`viridis`, `hot`, `magma`,
   `plasma`, `inferno`, `jet`) y se reescala al tamaño de la miniatura.
4. Se guardan el PNG, la matriz y sus estadísticas (media, máximo, desviación) y la
   escala de colores para dibujar la leyenda en el frontend.

El caché se indexa por (imagen, `grid_size`, `colormap`). En el visor, el mapa
muestra un *tooltip* con la densidad de la celda bajo el ratón.

### 6.3 Análisis consolidado (`analysis_service.py`)

`POST /images/{id}/analyze` ejecuta tejido + densidad reutilizando la misma
detección (una sola lectura de la miniatura) y guarda un resumen
`analysis_type = "full_analysis"` que muestra el panel de resultados. El frontend
enseña una barra de progreso estimada en cliente (con cancelación), porque el
backend resuelve el análisis en una sola petición.

### 6.4 Análisis de una región anotada (`annotation_analysis_service.py`)

Cualquier análisis puede ejecutarse sobre una anotación "como si fuese una WSI
aparte":

1. Se calcula el rectángulo delimitador de la forma y se lee **solo esa región**
   con `read_region_rgb`, eligiendo el nivel que la deja por debajo de ~2048 px.
2. En círculos y polígonos, los píxeles fuera de la forma se pintan de blanco para
   que la detección de tejido los ignore.
3. Se aplican los mismos algoritmos y los resultados se guardan con su
   `annotation_id`, con los PNG en `uploads/analysis/<imagen>/ann_<anotación>/`.

---

## 7. Clasificación de tejido con IA (InceptionV3)

### 7.1 El modelo

| Aspecto | Detalle |
|---|---|
| Arquitectura | **InceptionV3** de torchvision, con las salidas principal (`fc`, 2048 → 4) y auxiliar (`AuxLogits.fc`, 768 → 4) sustituidas por capas de 4 clases |
| Entrenamiento | *Fine-tuning* desde pesos de ImageNet (`InceptionV3/src/finetune.py`): 30 épocas, Adam (lr 1e-4), lotes de 16, pérdida = principal + 0,3 · auxiliar, aumentos (volteos, rotación ±15°, *color jitter*) |
| Datos | Fotos del dataset **BACH (ICIAR 2018)** de tejido mamario H&E: 2048 × 1536 px a ≈ 0,42 µm/px |
| Clases (orden de salida) | `benign`, `insitu`, `invasive`, `normal` (orden alfabético de `ImageFolder`) |
| Métricas de referencia | Exactitud 0,88 sobre 610 imágenes de validación (`InceptionV3/metricas.txt`); F1: Benign 0,87, InSitu 0,92, Invasive 0,94, Normal 0,76 |
| Pesos | `InceptionV3/HE_inceptionv3.pth`: `state_dict` puro de 97,8 MB, sin prefijos `module.`. SHA-256 `42515436…394a5e`. **No se versiona en Git** |

**Cuidado al interpretar las métricas.** La división train/val es aleatoria (no por
paciente) y en `finetune.py` ambos subconjuntos comparten el mismo `ImageFolder`,
por lo que la última transformación asignada se aplica a los dos. La cifra de 0,88
no equivale al rendimiento sobre WSI completas.

**Detalle de preprocesado crítico.** `finetune.py` crea el modelo con
`inception_v3(weights='IMAGENET1K_V1')`, y en ese caso torchvision activa
implícitamente `transform_input=True` (renormaliza internamente la entrada). El
script original `inference.py` crea el modelo sin pesos y lo deja en `False`, así que
**no reproduce el entrenamiento**. La integración fija `transform_input=True`
explícitamente.

### 7.2 Carga e inferencia: `inception_classifier.py`

Módulo aislado con la clase `InceptionClassifier` y la función `get_classifier()`:

- **Carga perezosa, una vez por proceso** (patrón *singleton* con *lock*): el modelo
  no se carga al arrancar el backend, sino en la primera clasificación.
- **Carga segura**: `torch.load(..., weights_only=True)`, que impide ejecutar código
  arbitrario desde el fichero. Acepta `state_dict` puro o envuelto y quita
  prefijos `module.`. Carga con `strict=True` para detectar cualquier desajuste.
- **Verificación**: calcula el SHA-256 del fichero y avisa en el log si no coincide
  con `INCEPTION_WEIGHTS_SHA256`.
- **Errores claros**: si falta el fichero o no encaja con la arquitectura lanza
  `ModelUnavailableError`, que los routers convierten en **HTTP 503** con un
  mensaje legible. El resto de la aplicación sigue funcionando.
- **Preprocesado** idéntico a la validación del entrenamiento:
  `RGB → Resize(299×299) → ToTensor → Normalize(media/desv. de ImageNet)`. Acepta
  imágenes PIL o arrays en gris, RGB o RGBA (`to_rgb_uint8`).
- **Dispositivo (CPU o GPU)**: `AI_DEVICE` admite `cpu`, `cuda` (alias `gpu`,
  `rocm`) y `auto`. PyTorch expone igual las GPU NVIDIA (CUDA) y AMD (ROCm), así
  que el código es el mismo. Al cargar, el modelo se lleva a la GPU y se hace una
  inferencia de prueba; si no hay GPU o falla (p. ej. arquitectura no soportada
  por esa versión de ROCm), **vuelve a CPU con un aviso** y la aplicación sigue
  funcionando. `gpu_info()` da el diagnóstico (versión y compilación de PyTorch,
  GPU detectada) que publica `GET /health/ai`.
- **Inferencia**: `predict_batch(imágenes, batch_size)` → array `(N, 4)` de
  probabilidades softmax, en `torch.inference_mode()`.
- **`info()`**: id del modelo, arquitectura, dataset, clases, tamaño de entrada,
  dispositivo usado y nombre de la GPU,
  versión de preprocesado, hash de los pesos y dispositivo. Se guarda con cada
  resultado.

### 7.3 Del WSI al mapa de clases: `ai_classification_service.py`

El modelo clasifica **imágenes sueltas** del tamaño de una foto de BACH. Para
aplicarlo a una WSI de gigapíxeles, el servicio la recorre así:

1. **Miniatura y máscara de tejido.** Se obtiene la miniatura (o la región de la
   anotación) y su máscara con el detector de la sección 6.1.
2. **Escala física del campo.** Con el µm/px de la WSI (`openslide.mpp-x`; si no
   existe se asume 0,5 y se indica en el resultado) se calcula cuántos píxeles de
   nivel 0 ocupa un campo como los del entrenamiento:
   `ancho = 2048 · 0,42 / mpp`, `alto = 1536 · 0,42 / mpp` (≈ **860 × 645 µm**).
   Así el modelo ve siempre el tejido a la misma escala que en el entrenamiento,
   tanto en la imagen completa como en una región anotada.
3. **Rejilla densa.** La región se divide en celdas del tamaño exacto del campo.
4. **Selección de celdas con tejido.** Se clasifican las celdas con al menos un
   35 % de tejido (`AI_MIN_TISSUE_FRAC`). El campo de cada una **se centra en el
   centroide de su tejido**, no en el centro geométrico, para que en los bordes del
   tejido el modelo vea tejido y no cristal. Las celdas de fondo no consumen
   presupuesto.
5. **Muestreo si hace falta.** Si hay más celdas con tejido que `AI_MAX_PATCHES`
   (1000), se elige un subconjunto repartido uniformemente entre ellas. En las WSI
   probadas (47-150 celdas con tejido) se analiza el **100 %**.
6. **Lectura e inferencia.** Los campos se leen de la WSI en paralelo (4 hilos;
   OpenSlide es seguro entre hilos) con `read_field_rgb` a 399 × 299 px (aspecto
   4:3) y se clasifican por bloques de 64, para acotar la memoria. El clasificador
   los lleva a 299 × 299, igual que en el entrenamiento.
7. **Relleno de celdas no evaluadas.** Las celdas de tejido que no se han analizado
   (bordes con poco tejido o celdas no muestreadas) toman la clase del campo
   analizado **más cercano** (transformada de distancia de SciPy). No cuentan en
   las estadísticas.
8. **Overlay.** Cada celda se pinta con el color de su clase: opacidad 140 si la
   evaluó el modelo y 80 si se rellenó por vecindad. El color se **recorta a la
   máscara de tejido**, así que sigue el contorno del tejido, lo cubre al 100 % y
   no se pinta sobre el cristal.
9. **Resumen y persistencia.** Se calculan los recuentos por clase, porcentajes,
   clase dominante, confianza media y probabilidad media por clase, y se guardan
   el PNG y el JSON en BD.

| Clase | Código | Color |
|---|---|---|
| Normal | `NORMAL` | verde |
| Benigno | `BENIGN` | azul |
| Carcinoma in situ | `INSITU` | ámbar |
| Carcinoma invasivo | `INVASIVE` | rojo |
| Fondo / no analizado | (no es salida de la red) | transparente |

**Rendimiento medido en CPU** (torch 2.12): lectura de un campo ≈ 11 ms (≈ 4 ms con
4 hilos) e inferencia ≈ 40 ms por campo. Una WSI de 156 000 × 64 000 px con 145
campos de tejido se clasifica en ≈ 11 s; una de 36 000 × 17 000 px, en ≈ 3 s.

### 7.4 Qué devuelve (`result_data` de `ai_classification`)

| Campo | Contenido |
|---|---|
| `model` | `info()` del clasificador (id, arquitectura, dataset, clases, versión de preprocesado, hash, dispositivo) |
| `classes`, `groups` | Por clase: código, nombre, color, nº de campos y % sobre los campos analizados |
| `dominant_class`, `dominant_group` | Clase con más campos |
| `mean_confidence`, `mean_probabilities` | Confianza media y probabilidad media por clase |
| `grid`, `rows`, `cols` | Matriz de etiquetas por celda (-1 = no evaluada) |
| `tissue_patches`, `total_patches` | Campos analizados y celdas de la rejilla |
| `sampling` | Celdas con tejido, analizadas e inferidas, cobertura, si hubo muestreo, tamaño del campo (px y µm), µm/px y su origen, y si el campo es mayor que la región anotada |
| `legend`, `background`, `disclaimer` | Leyenda, etiqueta de fondo y aviso de uso no diagnóstico |
| `tissue_detector_version` | Versión del detector de tejido usada (para invalidar la caché) |

Los porcentajes son **de campos evaluados**, no de superficie exacta.

### 7.5 Comprobar el modelo: `scripts/smoke_inception.py`

Script independiente (desde `backend/`):

```bash
python scripts/smoke_inception.py
python scripts/smoke_inception.py --images C:/ruta/BACH/Photos --limit 25
```

Carga el checkpoint, verifica el hash, comprueba que la salida es `(N, 4)`, finita y
suma 1, y que el *wrapper* da exactamente lo mismo que el pipeline de referencia de
torchvision. Con `--images` sobre carpetas `Benign/ InSitu/ Invasive/ Normal/` mide
la exactitud con `transform_input=True` y `False`, para confirmar el ajuste correcto
con datos etiquetados.

### 7.6 Limitaciones de la IA

- El modelo se entrenó con **fotos** de BACH, no con WSI; la equivalencia de escala
  (≈ 0,42 µm/px) es una aproximación razonable, no una validación.
- Cada campo cubre ≈ 0,56 mm²: el mapa tiene resolución de "campo", no celular.
- En anotaciones más pequeñas que un campo, el campo incluye contexto exterior a la
  región (`sampling.field_exceeds_region = true`).
- La clase "Normal" es la de menor F1 (0,76) en la validación original.

---

## 8. Anotaciones e interoperabilidad COCO

**Dibujo y edición** (`components/wsi/annotations/`):

- `AnnotationLayer.jsx` es una capa **SVG** sobre OpenSeadragon. Convierte
  coordenadas imagen ↔ pantalla en cada zoom o desplazamiento (`geometry.js`) y
  gestiona el dibujo de rectángulos, círculos y polígonos, además de una rejilla
  opcional.
- Las coordenadas se guardan **en píxeles de nivel 0**, así que son independientes
  del zoom: `rectangle {x, y, width, height}`, `circle {x, y, radius}`,
  `polygon {points: [[x, y], …]}`.
- `AnnotationToolbar` selecciona herramienta y color; `AnnotationPanel` lista las
  anotaciones y permite centrar, editar y eliminar cada una, además de **analizar
  la región** (tejido y densidad), lo que abre directamente su dashboard.
- `ClassificationModal` asigna una clase (y permite crear clases nuevas).
- `useAnnotations.js` mantiene el estado sincronizado con el backend.

**COCO** (`coco_service.py`):

- **Exportar** (`GET /images/{id}/export/coco`): `rectangle` → bbox + 4 esquinas;
  `circle` → polígono de 32 vértices; `polygon` → sus puntos. Cada anotación incluye
  `attributes` con `shape_type`, `color` y `label` para que exportar e importar
  recupere la forma original exacta (las herramientas COCO estándar ignoran ese
  campo).
- **Importar** (`POST /images/{id}/import/coco`): valida la estructura, crea las
  clases que no existan a partir de `categories` y reconstruye cada forma (usando
  `attributes` si está; si no, el polígono o el bbox).

---

## 9. Paleta de comandos

Con **Ctrl/Cmd + K** se abre una paleta con búsqueda (por título o palabras clave),
navegación con flechas y Enter. El catálogo está en `command_registry.py` y cada
comando tiene un **destino**:

| Destino | Comandos | Quién lo ejecuta |
|---|---|---|
| `backend` | Análisis completo, detectar tejido, generar mapa de densidad, clasificar con IA | `POST /commands/execute` → `command_executor.py`, que reutiliza los servicios de análisis |
| `frontend` | Abrir dashboard, mostrar/ocultar máscara y densidad, exportar/importar COCO, herramientas de dibujo, ir a la galería o a subir | La propia UI (`CommandPalette.jsx`), mediante refs imperativas de los controles |

---

## 10. Dashboard de análisis

`AnalyticsDashboard.jsx` pide `GET /images/{id}/analytics` (o
`/annotations/{id}/analytics`). `analytics_service.py` **solo agrega resultados ya
calculados** (no lanza análisis pesados), así que responde al instante. Para una
anotación sin análisis previo, el dashboard lo lanza automáticamente.

| Bloque | Qué muestra | De dónde sale |
|---|---|---|
| Resumen | Superficie de tejido (mm² y % de la imagen), nº de fragmentos, clase IA predominante, **% con patrón de carcinoma** (in situ + invasivo), nº y área de anotaciones | Máscara de tejido + escala + µm/px; resultado IA cacheado |
| Clasificación IA | Barras de Normal → Benigno → In situ → Invasivo con % y superficie aproximada (% × tejido), campos analizados y confianza media; botón para ejecutarla o repetirla | `ai_summary()` sobre el resultado IA vigente |
| Densidad del tejido | % de zonas con tejido de densidad baja (< 33 %), media y alta (> 66 %) y densidad media | Matriz del último mapa de densidad |
| Fragmentos de tejido | Superficie de las 10 mayores piezas de tejido (p. ej. cilindros de biopsia) | `fragment_areas_px` de la máscara × escala |
| Anotaciones por clase | Gráfico circular y tabla con nº y área (mm²) por clase | Anotaciones + área por forma (rectángulo, círculo, polígono por la fórmula del lazo) |
| Información de la imagen | Tamaño en mm y en píxeles, µm/px y aumento aproximado (0,25 µm/px ≈ 40x) | `width`, `height` y `openslide.mpp-x` |

Las superficies exigen conocer el µm/px de la WSI; si la imagen no lo incluye se
muestran porcentajes. Todas las gráficas se exportan a **PNG o SVG**.

---

## 11. Frontend por dentro

### 11.1 Rutas y sesión

| Ruta | Página | Acceso |
|---|---|---|
| `/login`, `/register` | Autenticación | Público |
| `/` | `ImageList`: tarjetas de las imágenes propias (nombre, dimensiones, niveles, tamaño, fecha), abrir, subir y eliminar | Protegida |
| `/upload` | `Upload`: arrastrar y soltar varias WSI con progreso por fichero | Protegida |
| `/settings` | `Settings`: nombre, email y contraseña | Protegida |
| `/viewer/:imageId` | `ImageViewer`: visor con anotaciones y análisis | Protegida |

`ProtectedRoute` redirige a `/login` si no hay sesión. `AuthProvider` expone
`useAuth()` (usuario, login, logout, register, actualizar perfil).

### 11.2 Comunicación con la API

- `services/api.js` crea la instancia Axios con la URL de `VITE_API_BASE_URL`
  (`frontend/.env`). Un interceptor de petición añade el JWT y otro de respuesta
  normaliza los errores (`utils/apiError.js`) y gestiona el 401.
- Hay un servicio por dominio: `authService`, `imageService`, `annotationService`,
  `tissueService`, `densityService`, `aiClassificationService`, `analysisService`,
  `annotationAnalysisService`, `analyticsService` y `commandService`.
- Los overlays (máscara, densidad, IA) se piden como *blob* con un parámetro
  anti-caché `_ts` y se convierten en *object URL*. El backend los sirve con
  `no-store` para que nunca se muestre un resultado antiguo.

### 11.3 El visor (`ImageViewer` + `WSIViewer`)

- `WSIViewer.jsx` crea OpenSeadragon con la URL DZI y las cabeceras de
  autenticación, y expone la instancia del visor al resto de controles.
- Cada control de análisis (`TissueMaskControl`, `DensityMapViewer`,
  `AIClassificationControl`) añade su PNG con `viewer.addSimpleImage`, ocupando todo
  el ancho de la imagen, de modo que queda alineado píxel a píxel con la WSI. Todos
  tienen botón de mostrar/ocultar, control de **opacidad** y botón de recalcular.
- `AIClassificationControl` muestra la clase predominante, las barras por clase, la
  cobertura ("N de M campos con tejido analizados · campo ≈ 860×645 µm"), el aviso
  de uso no diagnóstico y el modelo usado.
- `DensityMapViewer` permite elegir el tamaño de celda y el colormap, y dibuja la
  barra de colores y un *tooltip* con la densidad bajo el ratón.
- `AnalysisResultsPanel` + `AnalysisProgress` ejecutan el análisis consolidado con
  barra de progreso y cancelación.
- `ZoomControls` y `ViewerInfoBar` dan zoom y la información de la imagen.

---

## 12. Catálogo de la API

Todos los endpoints salvo salud, raíz, registro y login exigen
`Authorization: Bearer <token>`. La documentación interactiva está en `/docs`.

### Salud y autenticación

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/`, `/health/`, `/health/live`, `/health/ready` | Información y sondas de salud |
| GET | `/health/ai` | Estado de la IA: dispositivo pedido y usado, compilación de PyTorch (cpu/cuda/rocm), GPU detectada, pesos presentes (no carga el modelo) |
| POST | `/auth/register`, `/auth/login` | Devuelven token + usuario |
| GET / PATCH | `/auth/me` | Perfil del usuario / actualizar nombre, email o contraseña |
| POST / GET / DELETE | `/users/`, `/users/{id}` | Gestión de usuarios |

### Imágenes y visor

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/images/upload`, `/images/upload-multiple` | Subir una o varias WSI |
| GET | `/images/`, `/images/{id}` | Listar las propias / metadatos |
| DELETE | `/images/{id}` | Borrar imagen, ficheros y resultados |
| GET | `/images/{id}/dzi.dzi` | Descriptor Deep Zoom |
| GET | `/images/{id}/dzi_files/{level}/{col}_{row}.jpeg` | Tile |

### Anotaciones y COCO

| Método | Ruta | Descripción |
|---|---|---|
| GET / POST / DELETE | `/annotation-classes`, `/annotation-classes/{id}` | Clases de anotación |
| POST / GET | `/images/{id}/annotations` | Crear / listar anotaciones |
| PUT / DELETE | `/annotations/{id}` | Editar / eliminar |
| GET | `/images/{id}/export/coco` | Exportar a COCO |
| POST | `/images/{id}/import/coco` | Importar desde COCO |

### Análisis (imagen completa; los mismos existen bajo `/annotations/{id}/…`)

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/images/{id}/tissue-mask` · `/tissue-mask/stats` | PNG de la máscara · métricas JSON |
| POST | `/images/{id}/analyze/tissue` | Fuerza la detección de tejido |
| GET | `/images/{id}/density-map` · `/density-map/stats` | PNG del heatmap · métricas (`grid_size`, `colormap`) |
| POST | `/images/{id}/analyze/density` | Fuerza el mapa de densidad |
| POST / GET | `/images/{id}/analyze` · `/images/{id}/analysis` | Análisis consolidado: ejecutar · consultar |
| GET | `/images/{id}/ai-classification` · `/ai-classification/stats` | PNG del mapa de clases IA · resultado JSON |
| POST | `/images/{id}/analyze/ai` | Fuerza la clasificación IA (503 si faltan los pesos) |
| GET | `/images/{id}/analytics` | Datos del dashboard |

Los `GET` de análisis aceptan `force=true` para recalcular.

### Comandos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/commands`, `/commands/categories` | Catálogo y categorías |
| POST | `/commands/execute` | Ejecuta un comando de destino `backend` |

---

## 13. Cachés, versionado y almacenamiento

| Qué | Dónde | Cuándo se regenera |
|---|---|---|
| WSI subidas | `uploads/<user_id>/<nombre>` | — |
| Slides abiertos y tiles JPEG | Memoria (LRU: 8 slides, 2048 tiles) | Se expulsan por uso o al borrar la imagen |
| Máscara de tejido | `uploads/analysis/<img>/` + `analysis_results` | Si cambia `DETECTOR_VERSION` o falta el PNG |
| Mapa de densidad | Mismo directorio + `density_maps` (por `grid_size` y `colormap`) | Si cambia `DETECTOR_VERSION` o falta el PNG |
| Clasificación IA | `…/ai_classification.png` + `analysis_results` | Si cambia el id del modelo, la versión de preprocesado o la del detector de tejido |
| Resultados por anotación | `uploads/analysis/<img>/ann_<id>/` | Igual que los de imagen |

Gracias a este versionado, los resultados antiguos (por ejemplo, del clasificador
ResNet18 anterior o del detector de tejido previo) **nunca se muestran como si
fueran del algoritmo actual**: se recalculan solos la próxima vez que se piden.

Los pesos del modelo (`*.pth`, `*.pt`, `*.onnx`), `uploads/`, `.venv/` y los logs
están en `.gitignore`.

---

## 14. Pruebas

```bash
cd backend
python -m pytest
```

```bash
cd frontend
npm test
```

- **Backend (pytest, ~230 tests)**: una batería por dominio (auth, imágenes, subida
  múltiple, anotaciones, COCO, tejido, densidad, análisis por anotación, IA,
  analíticas, comandos, tiles…). Usan **SQLite** y sustituyen `OpenSlideService` y
  el clasificador por objetos falsos, así que no necesitan WSI reales ni el modelo.
  La excepción es un test que, **si existe el checkpoint**, carga el modelo real y
  comprueba que su salida es `(N, 4)` y válida.
- **Frontend (Vitest + Testing Library, ~150 tests)**: servicios de API y
  componentes clave (controles de análisis, dashboard, paleta, modales, hooks de
  anotación). Recharts se sustituye por *stubs*.

---

## 15. Puesta en marcha

### Requisitos

- Python 3.12 con un entorno virtual (en este proyecto, `.venv/` en la raíz).
- Node.js.
- PostgreSQL accesible según `DATABASE_URL`.
- El checkpoint `InceptionV3/HE_inceptionv3.pth` (o la ruta en
  `INCEPTION_WEIGHTS_PATH`). No está en Git: se descarga del release de GitHub
  (los scripts de Docker lo hacen solos). Sin él, todo funciona salvo la IA, que
  responde 503.

### En local (Windows / PowerShell)

Instalación (una vez):

```bash
cd backend; ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
cd frontend; npm.cmd install
```

Migraciones de la base de datos:

```bash
cd backend; ..\.venv\Scripts\python.exe -m alembic upgrade head
```

Backend (puerto 8000, documentación en `/docs`):

```bash
cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (otra terminal):

```bash
cd frontend; npm.cmd run dev -- --port 5175
```

La aplicación queda en http://localhost:5175. Notas:

- La URL del backend que usa el frontend se define en `frontend/.env`
  (`VITE_API_BASE_URL=http://localhost:8000`); si la cambias, reinicia Vite.
- En PowerShell usa `npm.cmd` / `npx.cmd` en lugar de `npm` / `npx`, que la
  política de ejecución de scripts puede bloquear.
- Para comprobar el modelo de IA, ver la [sección 7.5](#75-comprobar-el-modelo-scriptssmoke_inceptionpy);
  para los tests, la [sección 14](#14-pruebas).
- Para parar los servidores, pulsa **Ctrl + C** en cada terminal.

### Con Docker

`docker/docker-compose.yml` levanta tres servicios: `db` (PostgreSQL 16), `backend`
(aplica las migraciones al arrancar; puerto 8000) y `frontend` (build de Vite
servida por nginx; puerto 5173). Los pesos se montan en solo lectura desde
`../InceptionV3` en `/models`.

**En otro equipo basta con clonar el repositorio y ejecutar un script** desde
`docker/` (con Docker instalado y en marcha):

```bash
.\iniciar.ps1
```

En Linux / macOS: `sh iniciar.sh`. El script:

1. Crea `docker/.env` a partir de `.env.example` con una `SECRET_KEY` y una
   `DB_PASSWORD` aleatorias (si ya existe, solo rellena las que falten).
2. Descarga los pesos `HE_inceptionv3.pth` del **último release de GitHub** si no
   están y comprueba su SHA-256. Los pesos no se versionan en Git: hay que
   adjuntarlos a cada release. Si la descarga falla, la app arranca sin IA.
3. Pregunta dónde ejecutar la IA y lanza `docker compose ... up --build -d`:

| Opción | Fichero que se añade | Requisitos | PyTorch |
|---|---|---|---|
| CPU (por defecto) | — | Ninguno | `+cpu` |
| GPU NVIDIA | `docker-compose.gpu-nvidia.yml` | Driver NVIDIA; Linux con NVIDIA Container Toolkit o Windows con Docker Desktop (WSL2) | `+cu126` |
| GPU AMD | `docker-compose.gpu-amd.yml` | Solo Linux con ROCm (`/dev/kfd`, `/dev/dri`) | `+rocm7.1` |

Cada variante construye su propia imagen del backend (`wsi-tfg-backend:cpu`,
`:cuda`, `:rocm`) con el índice de PyTorch adecuado (`TORCH_INDEX_URL` en
`backend.Dockerfile`) y fija `AI_DEVICE`. Si la GPU no está disponible, la IA
funciona en CPU. Se comprueba en `http://localhost:8000/health/ai` o en la
etiqueta CPU/GPU del panel de IA. Detalles en `docker/README.md`.

---

## 16. Limitaciones y trabajo futuro

- **Validación clínica**: falta evaluar el modelo en WSI mamarias independientes,
  con anotaciones de patólogo y separación por paciente.
- **GPU AMD en Windows**: la GPU se usa con PyTorch + CUDA (NVIDIA) o + ROCm (AMD,
  solo Linux). Docker Desktop en Windows no expone GPU AMD, y PyTorch no tiene
  ROCm nativo en Windows: en ese caso la IA va en CPU. Una vía futura sería
  **ONNX Runtime + DirectML** fuera de Docker. Los tiempos en GPU no se han
  medido en este proyecto.
- **Análisis síncronos**: los análisis se resuelven dentro de la petición HTTP. Para
  WSI muy grandes convendría una cola de tareas con progreso real.
- **Detección de tejido en regiones sin cristal**: si una anotación cae entera
  dentro del tejido, no hay cristal de referencia y alguna zona muy pálida podría
  quedar fuera.
- **ESLint**: queda un aviso conocido por llamar a `load()` dentro de un `useEffect`
  en el dashboard.

---

## 17. Glosario

- **WSI (Whole Slide Image)**: digitalización completa de un portaobjetos a
  resolución de gigapíxeles, almacenada como pirámide de resoluciones.
- **Deep Zoom / DZI**: formato de pirámide de tiles que permite cargar solo la
  porción visible de una imagen enorme.
- **Tile**: fragmento cuadrado (aquí 256 px) de un nivel de la pirámide.
- **MPP (µm/px)**: micras por píxel; mide la escala física. 0,25 ≈ 40x; 0,5 ≈ 20x.
- **Nivel 0**: la resolución máxima de la WSI; todas las coordenadas se guardan en
  ella.
- **H&E**: tinción hematoxilina-eosina, la más común en histopatología.
- **Densidad óptica (OD)**: `-log10(I / I_fondo)`; cuánta luz absorbe la tinción
  respecto al cristal.
- **Otsu**: umbral automático que separa dos poblaciones de un histograma.
- **Histéresis**: umbral doble; lo que supera el débil se acepta solo si está unido a
  algo que supera el fuerte.
- **Campo**: región de ≈ 860 × 645 µm que el modelo clasifica de una vez.
- **InceptionV3**: red convolucional con módulos *Inception* y entrada de 299×299 px.
- **BACH (ICIAR 2018)**: dataset de imágenes de histología mamaria H&E en cuatro
  clases (Normal, Benigno, In situ, Invasivo).
- **Softmax**: función que convierte las salidas de la red en probabilidades que
  suman 1 (sin calibrar).
- **COCO**: formato JSON estándar de anotaciones de imagen.
- **JWT**: token firmado que identifica al usuario en cada petición.
- **Overlay**: capa RGBA semitransparente superpuesta a la imagen (máscara,
  heatmap o mapa de clases).