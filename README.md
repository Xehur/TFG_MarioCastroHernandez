# Documentación del Proyecto: Visor de Imágenes WSI con Análisis de Tejido e IA

## Índice

1. Introducción y objetivo
2. Visión general de la arquitectura
3. Tecnologías utilizadas
4. Backend: estructura y responsabilidades
5. Modelo de datos
6. Visualización de imágenes WSI (Deep Zoom)
7. Detección de tejido (visión por computador clásica)
8. Mapa de densidades de tejido
9. Clasificación de tejido con Inteligencia Artificial
10. Sistema de anotaciones y análisis por región
11. Importación / exportación COCO
12. Paleta de comandos y dashboard de analíticas
13. Autenticación y gestión de cuenta
14. Frontend: estructura y flujo
15. API: catálogo de endpoints
16. Estrategia de caché y rendimiento
17. Pruebas
18. Puesta en marcha (desarrollo)
19. Glosario

---

## 1. Introducción y objetivo

Este proyecto es un **visor web de imágenes de histopatología digital** (WSI, *Whole Slide Images*)
orientado al análisis de tejido. Permite subir imágenes de portaobjetos completos
(formatos `.svs`, `.tiff`, `.tif`, `.mrxs`), visualizarlas con zoom y desplazamiento
fluidos a resoluciones de gigapíxeles, dibujar anotaciones sobre zonas de interés, y
ejecutar análisis automáticos de tejido tanto con técnicas clásicas de visión por
computador como con un modelo de Inteligencia Artificial de clasificación histológica.

Las WSI son imágenes de dimensiones enormes (decenas de miles de píxeles por lado,
del orden de 35.000 x 16.000 px o más), por lo que el sistema está diseñado para no
cargar nunca la imagen completa en memoria: trabaja con pirámides de resolución,
miniaturas y lectura de regiones bajo demanda.

Objetivos funcionales principales:

- Subida y gestión de imágenes WSI.
- Visualización de gigapíxeles con OpenSeadragon (Deep Zoom).
- Anotaciones (rectángulo, círculo, polígono) con clases configurables.
- Detección automática de tejido frente a fondo.
- Generación de mapas de densidad de tejido.
- Clasificación del tejido mamario por IA (Normal, Benigno, In situ, Invasivo).
- Importación y exportación de anotaciones en formato COCO.
- Dashboard de analíticas y paleta de comandos.
- Autenticación de usuarios y gestión de la cuenta.

---

## 2. Visión general de la arquitectura

El sistema sigue una arquitectura cliente-servidor clásica de tres capas:

```
+---------------------------+        HTTP/JSON + Blobs        +---------------------------+
|        FRONTEND           |  <-------------------------->   |         BACKEND           |
|  React + Vite (SPA)       |                                 |  FastAPI (Python)         |
|  OpenSeadragon (WSI)      |                                 |  OpenSlide + PyTorch      |
|  Axios (cliente HTTP)     |                                 |  SQLAlchemy ORM           |
+---------------------------+                                 +-------------+-------------+
                                                                            |
                                                                            v
                                                              +---------------------------+
                                                              |     PostgreSQL            |
                                                              |  (metadatos, anotaciones, |
                                                              |   resultados de análisis) |
                                                              +---------------------------+
                                                              +---------------------------+
                                                              |   Sistema de ficheros     |
                                                              |  uploads/ (WSI + PNGs      |
                                                              |  de análisis cacheados)   |
                                                              +---------------------------+
```

- El **frontend** es una Single Page Application (SPA) que consume la API REST y
  renderiza los tiles de la imagen mediante OpenSeadragon.
- El **backend** expone una API REST, procesa las imágenes con OpenSlide, ejecuta los
  análisis (clásicos y de IA) y persiste metadatos y resultados.
- **PostgreSQL** almacena datos estructurados pequeños (metadatos de imágenes,
  anotaciones, resultados de análisis en formato JSON). Los binarios pesados (WSI y
  PNGs de overlays) viven en el sistema de ficheros, no en la base de datos.

---

## 3. Tecnologías utilizadas

### Backend (Python)

| Tecnología | Uso |
|------------|-----|
| FastAPI 0.104 | Framework web / API REST asíncrona |
| Uvicorn | Servidor ASGI |
| Pydantic 2 / pydantic-settings | Validación de esquemas y configuración |
| SQLAlchemy 2.0 | ORM |
| PostgreSQL (psycopg2) | Base de datos relacional |
| Alembic | Migraciones de base de datos |
| OpenSlide (openslide-python / openslide-bin) | Lectura de WSI y pirámides Deep Zoom |
| Pillow | Manipulación de imágenes |
| NumPy / SciPy | Cálculo numérico |
| scikit-image | Visión por computador clásica (densidad óptica, Otsu, histéresis, morfología) |
| Matplotlib | Colormaps de los heatmaps de densidad |
| PyTorch 2.x | Motor de inferencia del modelo de IA |
| torchvision | Arquitectura InceptionV3 y transformaciones de preprocesado |
| passlib + bcrypt | Hashing de contraseñas |
| python-jose | Tokens JWT |
| pytest / pytest-asyncio / httpx | Pruebas |
| black / flake8 / isort | Formato y linting |

### Frontend (JavaScript)

| Tecnología | Uso |
|------------|-----|
| React 19 | Librería de interfaz de usuario |
| Vite | Bundler y servidor de desarrollo |
| React Router 7 | Enrutado de la SPA |
| OpenSeadragon 6 | Visor de imágenes Deep Zoom (gigapíxeles) |
| Axios | Cliente HTTP |
| Recharts | Gráficos del dashboard de analíticas |
| lucide-react | Iconografía |
| Vitest + Testing Library | Pruebas unitarias y de componentes |
| ESLint + Prettier | Linting y formato |

---

## 4. Backend: estructura y responsabilidades

```
backend/app/
  main.py                 # Punto de entrada FastAPI: CORS, middleware, routers
  config.py               # Configuración (Pydantic Settings, variables .env)
  db.py                   # Motor SQLAlchemy y Base declarativa
  logging_config.py       # Configuración de logs
  middleware.py           # Middleware (cabecera de tiempo de proceso)

  core/
    deps.py               # Dependencias: sesión de BD y usuario autenticado
    security.py           # Hashing bcrypt y tokens JWT

  models/                 # Modelos ORM (SQLAlchemy)
    user.py, image.py, annotation.py, analysis.py

  schemas/                # Esquemas Pydantic (validación de entrada/salida)

  routers/                # Endpoints REST
    health.py, auth.py, users.py, images.py,
    annotations.py, coco.py, analysis.py, commands.py

  services/               # Lógica de negocio
    wsi/
      openslide_service.py  # Fachada sobre OpenSlide (dimensiones, tiles, patches)
      slide_cache.py        # Caché LRU de slides abiertos y tiles renderizados
    analysis/
      tissue_detection.py        # Detección de tejido (Otsu + morfología)
      tissue_service.py          # Orquestación + cacheo del análisis de tejido
      density_generation.py      # Cálculo del mapa de densidades por celdas
      density_service.py         # Orquestación + cacheo del mapa de densidades
      ai_classification_service.py  # Clasificación por IA (rejilla, overlay, caché)
      inception_classifier.py       # Carga e inferencia de InceptionV3 (4 clases)
      annotation_analysis_service.py # Análisis restringido a una anotación
    commands/
      command_registry.py   # Catálogo de comandos de la paleta
      command_executor.py   # Ejecución de comandos
    coco/                   # Importación/exportación COCO
    analytics/              # Agregación de métricas para el dashboard
```

Principios de diseño relevantes:

- **Separación routers / services**: los routers solo validan entrada, delegan en
  servicios y devuelven respuestas. La lógica vive en `services/`.
- **Interfaces sustituibles**: la detección de tejido y la generación de densidad
  definen una interfaz (`TissueDetector`, `DensityGenerator`) y una implementación por
  defecto, de modo que se pueden reemplazar sin tocar los endpoints.
- **Fachada de OpenSlide**: todo acceso a la WSI pasa por `OpenSlideService`, lo que
  aísla la librería y permite mockearla en tests.

---

## 5. Modelo de datos

Tablas principales (SQLAlchemy / PostgreSQL):

- **users**: `id`, `email` (único), `full_name`, `hashed_password`, `is_active`,
  `created_at`, `updated_at`.
- **images**: `id`, `filename` (único por usuario), `file_path` (ruta en disco, no binario:
  `uploads/<user_id>/<nombre>`),
  `user_id`, metadatos WSI (`width`, `height`, `level_count`, `downsamples`,
  `properties`), `file_size_mb`, timestamps. Relación en cascada con
  `analysis_results` y `density_maps`.
- **annotations**: `id`, `image_id`, `user_id`, `shape_type`
  (`rectangle` | `circle` | `polygon`), `coordinates` (JSON en píxeles de imagen),
  `label`, `color`, `class_id` (FK a `annotation_classes`), timestamps.
- **annotation_classes**: `id`, `name`, `color`, `description`, `user_id`. Clases
  configurables (por ejemplo "Tumor", "Estroma", "Necrosis").
- **analysis_results**: `id`, `image_id`, `annotation_id` (nullable; si es NULL el
  análisis es de imagen completa), `analysis_type` (por ejemplo `tissue_mask`,
  `ai_classification`), `result_data` (JSON con métricas y rutas de PNGs cacheados).
- **density_maps**: `id`, `image_id`, `annotation_id` (nullable), `grid_size`,
  `density_data` (JSON con la matriz de densidades y metadatos).

El uso de columnas JSON (`result_data`, `density_data`, `coordinates`, `properties`)
permite evolucionar el contenido de los análisis sin cambiar el esquema de la base de
datos.

---

## 6. Visualización de imágenes WSI (Deep Zoom)

La visualización de gigapíxeles se resuelve con el estándar **Deep Zoom Image (DZI)**:

1. El frontend inicializa OpenSeadragon apuntando al descriptor DZI de la imagen
   (`GET /images/{id}/dzi.dzi`).
2. OpenSeadragon solicita los tiles necesarios para la vista actual
   (`GET /images/{id}/dzi_files/{level}/{col}_{row}.jpeg`).
3. El backend genera esos tiles bajo demanda con `DeepZoomGenerator` de OpenSlide,
   escogiendo el nivel de la pirámide óptimo, y los sirve en JPEG.

De este modo solo se transfiere y renderiza la porción de la imagen visible al nivel
de zoom actual, nunca la imagen completa. El descriptor DZI se genera con el propio
`DeepZoomGenerator` para garantizar que la estructura de niveles, el tamaño de tile y
el solapamiento coinciden exactamente con los tiles servidos (evitando tiles en blanco
al cambiar de zoom).

---

## 7. Detección de tejido (visión por computador clásica)

Objetivo: separar el **tejido teñido** del **fondo** (el cristal del portaobjetos,
blanco o gris claro). Se resuelve con visión por computador clásica, **sin IA**,
porque para esta segmentación gruesa resulta más robusta que un modelo aprendido.

Técnica (`ClassicalTissueDetector`, en `tissue_detection.py`):

1. Se trabaja sobre una **miniatura** de la imagen (o de la región de una
   anotación), no sobre la WSI completa.
2. **Densidad óptica (OD) respecto al cristal**: se estima el color del cristal
   (percentil 99 de cada canal) y se calcula `OD = -log10(I / I_fondo)`. El cristal
   tiene OD ≈ 0 y cualquier tinción, aunque sea pálida, tiene OD > 0.
3. **Umbral con histéresis**:
   - *Fuerte*: Otsu sobre la OD (recortada al percentil 99,5 para que unos pocos
     píxeles extremos no lo desplacen). Marca el tejido claramente teñido.
   - *Débil*: justo por encima del ruido del cristal (mediana + 6·MAD de la OD
     del fondo, mínimo 0,035) o con algo de color (saturación > 0,08).
   - Se conservan las regiones débiles **conectadas** a alguna región fuerte.
     Así se recupera el tejido pálido (grasa, estroma laxo, eosina clara), que un
     único umbral de Otsu dejaba fuera, sin aceptar manchas aisladas del cristal.
4. **Artefactos**:
   - *Tinta de rotulador* (tonos amarillo-verde-cian, fuera de la gama H&E): se
     excluye, incluidas sus zonas pálidas.
   - *Franjas del escáner*: se eliminan las franjas finas pegadas a un borde de la
     imagen, aunque toquen el tejido; la punta de tejido que entra en ellas se
     conserva.
5. **Limpieza morfológica**: cierre, relleno de huecos interiores (vacuolas de
   grasa) y eliminación de objetos pequeños, con tamaños relativos al área de la
   miniatura.

El resultado incluye la máscara binaria, el porcentaje de tejido, los umbrales de
OD, el color estimado del cristal y el porcentaje de tinta excluida. La máscara se
convierte en un overlay RGBA semitransparente (verde por defecto) que se
superpone sobre la imagen en el visor. Tarda menos de 1 s con la miniatura de
2048 px.

Cada resultado guarda `detector_version`. Las máscaras, los mapas de densidad y
las clasificaciones IA generados con otra versión del detector se regeneran
automáticamente.

Nota de diseño: existió una variante experimental de detección de tejido por IA que se
descartó por segmentar peor que el método clásico. La IA se reserva exclusivamente
para la *clasificación* histológica (sección 9), no para el *enmascarado* del tejido.

---

## 8. Mapa de densidades de tejido

Construido sobre la máscara de tejido de la sección anterior
(`density_generation.py`):

1. Se parte de la máscara binaria de tejido.
2. La imagen se divide en una **rejilla de celdas cuadradas** cuyo tamaño
   (`grid_size`) se expresa en píxeles de la imagen base (por defecto 256).
3. Para cada celda se calcula la **densidad de tejido** = fracción de píxeles de la
   celda clasificados como tejido, un valor en el rango [0, 1].
4. La matriz de densidades se colorea con un **colormap** (viridis, hot, etc.,
   mediante Matplotlib) generando un heatmap RGBA semitransparente alineado con la
   imagen base.

El heatmap se cachea en disco (PNG) y la matriz con sus metadatos en la tabla
`density_maps`, indexado por `(image_id, grid_size, colormap)`.

---

## 9. Clasificación de tejido con Inteligencia Artificial

> **Uso académico / de investigación.** Las predicciones no constituyen un
> diagnóstico clínico y la confianza softmax no está calibrada.

### 9.1 Qué modelo se usa y de dónde viene

- **Arquitectura**: **InceptionV3** (`torchvision.models.inception_v3`) con las
  capas de salida principal y auxiliar sustituidas por capas de 4 clases.
- **Entrenamiento**: *fine-tuning* propio a partir de los pesos de ImageNet
  (`InceptionV3/src/finetune.py`) sobre las fotos del dataset **BACH (ICIAR 2018)**
  de tejido mamario teñido con H&E.
- **Pesos**: `InceptionV3/HE_inceptionv3.pth` (`state_dict`, 97,8 MB, SHA-256
  `42515436…394a5e`). No se versiona en Git; la ruta es configurable con
  `INCEPTION_WEIGHTS_PATH`. Se carga con `torch.load(weights_only=True)`.
- **Métricas de referencia** (`InceptionV3/metricas.txt`): exactitud 0,88 sobre 610
  imágenes de validación aleatoria (no separada por paciente, y con la misma
  transformación en entrenamiento y validación por compartir el `ImageFolder`).
  No equivale al rendimiento sobre WSI completas.

### 9.2 Qué clasifica

El modelo clasifica cada campo en **4 categorías** (orden exacto de salida):
`BENIGN` (Benigno), `INSITU` (Carcinoma in situ), `INVASIVE` (Carcinoma invasivo)
y `NORMAL` (Normal). Cada clase es su propio grupo de presentación, con un color
único compartido por overlay, leyenda y barras.

"Fondo / no analizado" **no es una salida de la red**: identifica las celdas sin
tejido suficiente, que se excluyen de la inferencia y quedan transparentes.

### 9.3 Preprocesado y escala

- Preprocesado idéntico a la validación del entrenamiento:
  `RGB → Resize(299×299) → ToTensor → Normalize(ImageNet)`, con
  `transform_input=True`. Este último detalle importa: al crear el modelo con
  pesos de ImageNet, torchvision lo activa de forma implícita, mientras que
  `InceptionV3/src/inference.py` lo deja desactivado y no reproduce el
  entrenamiento.
- Las fotos de BACH miden 2048×1536 px a ≈0,42 µm/px (≈860×645 µm). En la WSI,
  cada celda de la rejilla lee **un campo real de ese mismo tamaño físico**
  (`OpenSlideService.read_field_rgb`, nivel de pirámide adecuado), que el
  clasificador reduce a 299×299 igual que en el entrenamiento. Tamaño y MPP
  configurables con `AI_FIELD_MPP`, `AI_FIELD_WIDTH_PX` y `AI_FIELD_HEIGHT_PX`.
  Si la WSI no expone `openslide.mpp-x`, se asume 0,5 µm/px y se indica en el
  resultado (`sampling.mpp_source = "default"`).

### 9.4 Flujo (`ai_classification_service.py`)

1. Miniatura de la imagen (o de la región anotada) y máscara de tejido clásica.
2. Rejilla **densa** de celdas del tamaño exacto del campo (una celda = un campo).
3. Solo las celdas con al menos `AI_MIN_TISSUE_FRAC` (35 %) de tejido se
   clasifican: el presupuesto nunca se gasta en fondo. Si superan
   `AI_MAX_PATCHES` (1000 por defecto), se elige un subconjunto repartido
   uniformemente **entre las celdas de tejido**, y las no evaluadas se pintan en el
   overlay de forma atenuada con la clase del campo evaluado más cercano (no
   cuentan en las estadísticas).
4. Los campos se leen de la WSI en paralelo (`AI_READ_WORKERS`, 4 hilos) y se
   clasifican por bloques (`inception_classifier.py`, `predict_batch → (N, 4)`),
   con la memoria acotada.
5. Overlay RGBA por clase y resumen: distribución por clase, clase dominante,
   confianza media, probabilidades medias y **cobertura** (`sampling`: celdas con
   tejido, analizadas, inferidas, fracción cubierta, tamaño del campo en µm y si
   el campo excede la región anotada).

Los porcentajes son **de campos evaluados**, no de superficie. En anotaciones
más pequeñas que un campo (~0,86 mm), el campo incluye contexto exterior a la
región (`sampling.field_exceeds_region = true`).

### 9.5 Caché y versionado

Cada resultado guarda `model.id`, `preprocessing_version`, el hash de los pesos y
los parámetros de muestreo. Un resultado de otro modelo (por ejemplo, del ResNet18
anterior) no se sirve: se regenera automáticamente.

### 9.6 Hardware

La inferencia se ejecuta en **CPU** (≈40–50 ms por campo con torch 2.12 CPU, lectura incluida). El
modelo se carga una vez por proceso, de forma perezosa. `AI_DEVICE` queda
preparado para añadir aceleración en la GPU AMD (DirectML / ONNX Runtime) en una
fase posterior. Si faltan los pesos, los endpoints de IA responden **503**.

---

## 10. Sistema de anotaciones y análisis por región

- El usuario dibuja anotaciones sobre la imagen con tres herramientas:
  **rectángulo, círculo y polígono**. Las coordenadas se guardan en píxeles de la
  imagen base.
- Cada anotación puede asignarse a una **clase** configurable (nombre + color).
- Cualquiera de los tres análisis (detección de tejido, mapa de densidades y
  clasificación por IA) puede ejecutarse **restringido a la región de una anotación**,
  no solo sobre la imagen completa (`annotation_analysis_service.py`).
- Para formas no rectangulares (círculo, polígono), los píxeles fuera de la forma se
  excluyen (se ponen a blanco) para que el análisis no considere tejido fuera de la
  región marcada.

---

## 11. Importación / exportación COCO

El sistema interopera con el formato estándar **COCO** (Common Objects in Context) para
anotaciones:

- **Exportación**: `GET /images/{id}/export/coco` genera un JSON COCO con las
  anotaciones de la imagen.
- **Importación**: se suben anotaciones en formato COCO y se crean en la imagen.

Esto permite intercambiar anotaciones con otras herramientas del ecosistema de visión
por computador y de anotación de imagen médica.

---

## 12. Paleta de comandos y dashboard de analíticas

- **Paleta de comandos**: una interfaz tipo "command palette" que centraliza las
  acciones disponibles (ejecutar análisis completo, detectar tejido, generar mapa de
  densidades, clasificar con IA, abrir el dashboard, alternar overlays, exportar/
  importar COCO, seleccionar herramientas de dibujo, navegar). El catálogo se define en
  `command_registry.py` y se ejecuta desde `command_executor.py`.
- **Dashboard de analíticas**: agrega métricas de los análisis ya realizados (no
  ejecuta análisis pesados, salvo que se pida la clasificación IA) y las presenta
  con gráficos (Recharts) exportables a PNG/SVG, priorizando datos fáciles de
  interpretar:
  - **Resumen**: superficie de tejido en mm² (y % de la imagen), nº de fragmentos
    de tejido, clase IA predominante, % de tejido con patrón de carcinoma
    (in situ + invasivo) y nº/área de anotaciones.
  - **Clasificación IA**: proporción y superficie aproximada de cada clase
    (Normal → Benigno → In situ → Invasivo), campos analizados y confianza media.
  - **Densidad del tejido**: zonas con tejido de densidad baja, media y alta.
  - **Fragmentos de tejido**: superficie de cada pieza (p. ej. cilindros de biopsia).
  - **Anotaciones por clase**: número y área anotada de cada clase.
  - **Información de la imagen**: tamaño en mm, µm/px y aumento aproximado.

  Las superficies usan la resolución física de la WSI (`openslide.mpp-x`); si la
  imagen no la tiene, se muestran porcentajes.

---

## 13. Autenticación y gestión de cuenta

- **Autenticación por JWT**: el usuario se registra o inicia sesión
  (`POST /auth/register`, `POST /auth/login`) y recibe un token de acceso (JWT firmado
  con HS256). El token se envía como cabecera `Authorization: Bearer <token>` en las
  peticiones protegidas.
- Las contraseñas se almacenan **hasheadas con bcrypt** (nunca en texto plano) y jamás
  se exponen en las respuestas.
- El token y el usuario se guardan en `localStorage` del navegador; al recargar la app
  se rehidrata la sesión validando el token contra `GET /auth/me`.
- **Gestión de la cuenta**: la página de Ajustes permite modificar el nombre, el email
  y la contraseña (`PATCH /auth/me`). El cambio de contraseña exige verificar la
  contraseña actual; el cambio de email valida que no esté en uso.
- Las imágenes están vinculadas a su propietario: cada usuario solo ve y puede eliminar
  sus propias imágenes.

---

## 14. Frontend: estructura y flujo

```
frontend/src/
  main.jsx                 # Bootstrap de React
  App.jsx                  # Rutas de la SPA (React Router)
  index.css / App.css      # Estilos globales y tokens de diseño

  context/                 # Contexto de autenticación (AuthProvider, useAuth)
  config/                  # Configuración (URL base de la API, claves)
  services/                # Clientes de la API (uno por dominio)
    api.js                 # Instancia Axios con interceptores (token, errores)
    authService, imageService, annotationService,
    tissueService, densityService, aiClassificationService,
    analysisService, analyticsService, commandService, ...
  utils/                   # Helpers, manejo de errores de API, monitor de rendimiento

  pages/
    Login/  Register/      # Autenticación
    ImageList/             # Galería de imágenes (con subir y eliminar)
    Upload/                # Subida (drag & drop)
    Settings/              # Ajustes de la cuenta
    ImageViewer/           # Visor principal (OpenSeadragon + paneles)

  components/
    auth/                  # UserMenu, ProtectedRoute
    upload/                # Zona de arrastrar y soltar
    wsi/                   # Visor y controles
      WSIViewer, ZoomControls, ViewerInfoBar
      annotations/         # Herramientas, capa, panel, modales COCO/clasificación
      analysis/            # Controles de máscara de tejido, densidad,
                           # clasificación IA, dashboard, paleta de comandos,
                           # panel de resultados y progreso
```

Rutas principales (todas salvo login/registro protegidas por `ProtectedRoute`):

- `/login`, `/register`: autenticación.
- `/` : galería de imágenes (`ImageList`). Permite ver, subir y eliminar imágenes, y
  acceder a los Ajustes desde el menú de usuario.
- `/upload`: subida de imágenes.
- `/settings`: ajustes de la cuenta.
- `/viewer/:imageId`: visor de la imagen con todas las herramientas de anotación y
  análisis.

Flujo típico del usuario:

1. Inicia sesión o se registra.
2. Sube una o varias imágenes WSI (drag & drop). El backend extrae metadatos con
   OpenSlide y las registra.
3. Abre una imagen en el visor; OpenSeadragon carga los tiles Deep Zoom bajo demanda.
4. Dibuja anotaciones y/o ejecuta análisis (tejido, densidad, IA) sobre la imagen
   completa o una región. Los overlays resultantes se superponen sobre la imagen.
5. Consulta el dashboard de analíticas, exporta/importa anotaciones COCO, o gestiona su
   cuenta.

Comunicación con el backend: todos los servicios usan una instancia central de Axios
(`api.js`) que inyecta el token JWT y normaliza los errores. Las imágenes de overlay
(máscaras, heatmaps, mapas de clases) se piden como *blobs* con un parámetro
anti-caché (`_ts`) para forzar siempre la versión recién generada.

---

## 15. API: catálogo de endpoints

### Salud
- `GET /` — información de la API.
- `GET /health/`, `GET /health/live`, `GET /health/ready` — sondas de salud.

### Autenticación (`/auth`)
- `POST /auth/register` — registro, devuelve token + usuario.
- `POST /auth/login` — login, devuelve token + usuario.
- `GET  /auth/me` — perfil del usuario autenticado.
- `PATCH /auth/me` — actualizar nombre, email y/o contraseña.

### Usuarios (`/users`)
- `POST /users/`, `GET /users/`, `GET /users/{id}`, `DELETE /users/{id}`.

### Imágenes (`/images`)
- `POST /images/upload` — subir una imagen.
- `POST /images/upload-multiple` — subir varias (drag & drop).
- `GET  /images/` — listar las imágenes del usuario.
- `GET  /images/{id}` — metadatos de una imagen.
- `DELETE /images/{id}` — eliminar una imagen (registro + ficheros + caché).
- `GET  /images/{id}/dzi.dzi` — descriptor Deep Zoom.
- `GET  /images/{id}/dzi_files/{level}/{col}_{row}.jpeg` — tile Deep Zoom.

### Anotaciones (`/`)
- `GET/POST/DELETE /annotation-classes` — clases de anotación.
- `POST /images/{id}/annotations`, `GET /images/{id}/annotations` — crear/listar.
- `PUT/DELETE /annotations/{id}` — actualizar/eliminar.

### Análisis (`/`) — imagen y anotación
- Detección de tejido: `GET /images/{id}/tissue-mask`, overlay y `POST` de análisis;
  equivalentes en `/annotations/{id}/tissue-mask`.
- Mapa de densidades: `GET /images/{id}/density-map` (+ heatmap y `POST`);
  equivalentes para anotaciones.
- Clasificación IA: `GET /images/{id}/ai-classification` (+ overlay y `POST`);
  equivalentes para anotaciones.
- Análisis completo: `POST` que encadena los análisis anteriores.

### COCO (`/`)
- `GET  /images/{id}/export/coco` — exportar anotaciones a COCO.
- `POST` de importación COCO.

### Comandos (`/commands`)
- `GET  /commands` — catálogo de comandos.
- `GET  /commands/categories` — categorías.
- `POST /commands/execute` — ejecutar un comando.

Todos los endpoints de negocio requieren autenticación (JWT). Los PNGs generados por
los análisis se sirven con cabeceras `no-store` para evitar que el navegador muestre
overlays obsoletos.

---

## 16. Estrategia de caché y rendimiento

- **Caché de slides y tiles** (`slide_cache.py`): una caché LRU thread-safe mantiene
  abiertos los últimos `OpenSlideService`/`DeepZoomGenerator` (abrir una WSI es
  costoso) y los últimos tiles JPEG renderizados. Al eliminar una imagen se expulsa su
  slide de la caché antes de borrar el fichero (en Windows no se puede borrar un
  fichero mientras OpenSlide lo mantiene abierto).
- **Cacheo de análisis en disco/BD**: los overlays (máscara, heatmap, mapa de clases)
  se guardan como PNG y sus métricas en la base de datos, indexados por parámetros
  (por ejemplo `grid_size` y `colormap` en densidad). Reejecutar un análisis con los
  mismos parámetros reutiliza el resultado cacheado.
- **Anti-caché de navegador**: los tiles estáticos sí se cachean en el navegador
  (`max-age`), pero los PNGs dinámicos de análisis se sirven con
  `no-store, no-cache, must-revalidate` y el frontend añade un parámetro `_ts` para
  garantizar que siempre se muestra la versión recién generada.
- **Streaming en la subida**: los ficheros grandes se guardan por chunks (8 MB) sin
  cargarlos enteros en memoria.
- **Trabajo sobre miniaturas**: los análisis se calculan sobre miniaturas o regiones,
  y solo la clasificación IA lee parches reales a la magnificación exacta.

---

## 17. Pruebas

- **Backend** (`pytest`): baterías por dominio (`test_auth`, `test_images`,
  `test_users`, `test_annotations`, `test_tissue_analysis`, `test_density_analysis`,
  `test_ai_classification`, `test_coco`, `test_commands`, `test_tiles`,
  `test_openslide_service`, etc.). Se usa una base de datos SQLite en memoria y se
  mockea `OpenSlideService` con slides falsos para no depender de ficheros WSI reales.
- **Frontend** (`vitest` + Testing Library): pruebas de los servicios de API y de
  componentes clave (controles de análisis, panel de anotaciones, dashboard, paleta de
  comandos, modales COCO/clasificación, hooks de anotación).

---

## 18. Puesta en marcha (desarrollo)

Requisitos: Python con un entorno virtual, Node.js y una base de datos PostgreSQL
accesible según `DATABASE_URL` en `backend/app/config.py` (o variables `.env`).

Backend:

```
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```
cd frontend
npm install
npm run dev
```

Por defecto el backend escucha en `http://localhost:8000` (documentación interactiva en
`/docs`) y el frontend en `http://localhost:5173`. La configuración de CORS del backend
permite el origen del frontend en desarrollo.

Consulte también `README.md` y `Ejecutar_GUIA.md` en la raíz del proyecto para
instrucciones adicionales de arranque.

---

## 19. Glosario

- **WSI (Whole Slide Image)**: digitalización completa de un portaobjetos de histología
  a resolución de gigapíxeles.
- **Deep Zoom / DZI**: formato piramidal de tiles que permite navegar imágenes enormes
  cargando solo la porción visible.
- **Tile**: fragmento cuadrado de la imagen a un nivel de zoom concreto.
- **MPP (microns per pixel)**: micras por píxel; mide la magnificación física de la
  imagen. 0.5 MPP equivale aproximadamente a 20x.
- **Otsu**: método automático de umbralización que separa dos poblaciones de
  intensidad (aquí, tejido frente a fondo).
- **Densidad óptica (OD)**: `-log10(I / I_fondo)`; mide cuánta luz absorbe la
  tinción respecto al cristal.
- **Histéresis**: umbral doble; los píxeles por encima del umbral débil se aceptan
  solo si están conectados a píxeles por encima del umbral fuerte.
- **H&E**: tinción de Hematoxilina-Eosina, la más común en histopatología.
- **InceptionV3**: arquitectura convolucional con módulos *Inception* y entrada de 299×299 px.
- **BACH (ICIAR 2018)**: dataset de fotos de histología mamaria H&E en 4 clases
  (Normal, Benigno, In situ, Invasivo) usado para entrenar el clasificador de IA.
- **COCO**: formato estándar de representación de anotaciones de imagen.
- **JWT**: JSON Web Token, mecanismo de autenticación basado en tokens firmados.
- **Overlay**: capa RGBA semitransparente que se superpone sobre la imagen para mostrar
  el resultado de un análisis (máscara, heatmap, mapa de clases).
