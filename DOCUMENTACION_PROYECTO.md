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
- Clasificación del tejido por IA en categorías histológicas.
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
| scikit-image | Visión por computador clásica (Otsu, morfología, HSV) |
| Matplotlib | Colormaps de los heatmaps de densidad |
| PyTorch 2.x | Motor de inferencia del modelo de IA |
| timm | Carga de la arquitectura ResNet18 y del modelo preentrenado |
| safetensors / huggingface_hub | Descarga y carga de los pesos del modelo desde Hugging Face |
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
      ai_classification_service.py  # Clasificación por IA (ResNet18)
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
- **images**: `id`, `filename` (único), `file_path` (ruta en disco, no binario),
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

Objetivo: separar el **tejido teñido** del **fondo** (típicamente blanco/gris claro del
cristal del portaobjetos). Se resuelve con visión por computador clásica, **sin IA**,
porque resulta más robusta y precisa que un modelo aprendido para esta tarea concreta
de segmentación gruesa.

Técnica (`ClassicalTissueDetector`, en `tissue_detection.py`):

1. Se trabaja sobre una **miniatura** de la imagen (o de la región de una anotación),
   no sobre la WSI completa.
2. **Umbral de Otsu sobre el canal de saturación (HSV)**: el tejido teñido (H&E u
   otras tinciones) presenta mayor saturación de color que el fondo.
3. **Umbral de Otsu sobre la intensidad (escala de grises)**: el tejido es más oscuro
   que el fondo claro.
4. **Combinación**: un píxel se considera tejido si tiene suficiente color O es
   notablemente oscuro (`mask_saturación OR mask_intensidad`).
5. **Limpieza morfológica**: cierre (`closing`) para unir regiones cercanas, relleno
   de huecos internos (`remove_small_holes`) y eliminación de objetos pequeños
   (`remove_small_objects`) para descartar ruido.

El resultado incluye la máscara binaria, el porcentaje de tejido y los umbrales
calculados. La máscara se convierte en un overlay RGBA semitransparente (verde por
defecto) que se superpone sobre la imagen en el visor.

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

### 9.1 Qué modelo se usa y de dónde viene

- **Modelo**: `1aurent/resnet18.tiatoolbox-kather100k`, alojado en Hugging Face y
  cargado mediante la librería `timm` (identificador
  `hf-hub:1aurent/resnet18.tiatoolbox-kather100k`).
- **Arquitectura**: **ResNet18** (red neuronal convolucional residual de 18 capas).
- **Origen / procedencia**: es un modelo de **TIAToolbox** (The Tissue Image Analytics
  toolbox, del grupo de investigación en análisis de imagen de tejido de la
  Universidad de Warwick), republicado en Hugging Face en formato `timm`/safetensors.
- **Dataset de entrenamiento**: **NCT-CRC-HE-100K** (conocido como "kather100k"), un
  conjunto de ~100.000 parches de 224x224 px de histología de cáncer colorrectal
  teñida con Hematoxilina-Eosina (H&E). Licencia CC-BY-4.0.

### 9.2 Qué clasifica

El modelo clasifica cada parche en **9 categorías histológicas** (orden exacto del
modelo): `BACK` (fondo), `NORM` (mucosa normal), `DEB` (debris/necrosis), `TUM`
(tumoral / epitelio de adenocarcinoma), `ADI` (tejido adiposo), `MUC` (moco), `MUS`
(músculo liso), `STR` (estroma), `LYM` (linfocitos).

Para la presentación al usuario, esas 9 clases finas se agrupan en **5 categorías de
alto nivel**: **Tumoral, Estroma, No tumoral, Necrosis y Fondo**. El overlay pintado
sobre la imagen, la leyenda y las barras del resumen usan siempre el color del grupo,
de modo que lo que se ve sobre la imagen coincide exactamente con la leyenda.

### 9.3 Cómo se aplica (muestreo consciente de la magnificación)

Este es el punto técnicamente más delicado. El modelo fue entrenado con parches de
**224 x 224 px a ~0.5 µm/px (magnificación 20x)**. Si se le entregan parches a otra
escala, sus predicciones dejan de ser fiables.

Estrategia implementada en `ai_classification_service.py`
(`classify_slide_region`):

1. Se calcula la magnificación real de la WSI mediante los metadatos
   (`openslide.mpp-x`); si no existen, se asume 0.5 µm/px.
2. Se determina el tamaño del parche en píxeles de nivel 0 necesario para representar
   224 px **a la magnificación objetivo de 0.5 MPP** (`patch_px = 224 * (0.5 / mpp)`).
3. La región a clasificar (imagen completa o bounding box de una anotación) se cubre
   con una rejilla de celdas.
4. Cada celda se filtra con la **máscara de tejido clásica**: si no contiene tejido
   suficiente (umbral configurable), se descarta sin inferencia.
5. Para las celdas con tejido se lee un **parche REAL de 224x224 a 0.5 MPP**
   directamente de la WSI (`OpenSlideService.read_patch_rgb`, que escoge el nivel de la
   pirámide adecuado), en lugar de aplastar una miniatura.
6. Los parches se clasifican en lotes con PyTorch; se aplica softmax y argmax para
   obtener clase y confianza por celda.
7. Se construye un overlay RGBA (mapa de clases) a la resolución de la miniatura y un
   resumen de distribución por clase y por grupo.

Ventaja clave: **la imagen completa y una región anotada se clasifican a la misma
magnificación** que la de entrenamiento, por lo que los resultados son coherentes
entre ambos ámbitos. En imágenes muy grandes se acota el número de parches muestreando
celdas representativas, manteniendo siempre la magnificación correcta.

### 9.4 Consideraciones de hardware

El modelo (ResNet18) es ligero y se ejecuta cómodamente en **CPU**, por lo que no
requiere GPU. La inferencia es perezosa: el modelo se carga la primera vez que se usa
y se cachea en memoria del proceso. Los pesos se descargan automáticamente de Hugging
Face en el primer arranque.

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
- **Dashboard de analíticas**: agrega métricas de los análisis realizados y las
  presenta con gráficos (Recharts) en el frontend.

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
- **H&E**: tinción de Hematoxilina-Eosina, la más común en histopatología.
- **ResNet18**: arquitectura de red neuronal convolucional residual de 18 capas.
- **NCT-CRC-HE-100K / kather100k**: dataset de ~100.000 parches de histología
  colorrectal H&E usado para entrenar el clasificador de IA.
- **COCO**: formato estándar de representación de anotaciones de imagen.
- **JWT**: JSON Web Token, mecanismo de autenticación basado en tokens firmados.
- **Overlay**: capa RGBA semitransparente que se superpone sobre la imagen para mostrar
  el resultado de un análisis (máscara, heatmap, mapa de clases).
