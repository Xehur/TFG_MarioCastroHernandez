"""
Servicio de paleta de comandos (Sprint 6, issue 36).

Expone un catálogo de acciones disponibles en la aplicación (comandos) con
metadatos para representarlos en la paleta del frontend (Ctrl/Cmd+K), y un
ejecutor para los comandos que se resuelven en el servidor.

Cada comando declara:
- id, name, description, category, icon (nombre de icono lucide).
- target: "frontend" (lo maneja la UI) o "backend" (ejecutable vía API).
- method / endpoint: referencia informativa del endpoint asociado.
- action / route: pista para que la UI sepa qué hacer con comandos frontend.
- params: parámetros esperados (name, type, required, description).
- keywords: términos extra para la búsqueda.
"""
from typing import Any, Dict, List, Optional

CATEGORY_ANALYSIS = "Análisis"
CATEGORY_VISUALIZATION = "Visualización"
CATEGORY_ANNOTATIONS = "Anotaciones"
CATEGORY_NAVIGATION = "Navegación"

TARGET_FRONTEND = "frontend"
TARGET_BACKEND = "backend"


def _param(name: str, type_: str, required: bool, description: str) -> Dict[str, Any]:
    return {
        "name": name,
        "type": type_,
        "required": required,
        "description": description,
    }


_IMAGE_ID_PARAM = _param("image_id", "int", True, "Identificador de la imagen")

# Catálogo estático de comandos disponibles.
COMMANDS: List[Dict[str, Any]] = [
    # --- Análisis (ejecutables en el servidor) -----------------------------
    {
        "id": "run-full-analysis",
        "name": "Analizar imagen (completo)",
        "description": "Ejecuta la detección de tejido y el mapa de densidades y guarda el resumen.",
        "category": CATEGORY_ANALYSIS,
        "icon": "Activity",
        "target": TARGET_BACKEND,
        "method": "POST",
        "endpoint": "/images/{image_id}/analyze",
        "action": None,
        "route": None,
        "params": [_IMAGE_ID_PARAM],
        "keywords": ["analisis", "tejido", "densidad", "analyze", "completo"],
    },
    {
        "id": "detect-tissue",
        "name": "Detectar tejido",
        "description": "Genera la máscara de tejido de la imagen (tejido vs fondo).",
        "category": CATEGORY_ANALYSIS,
        "icon": "Layers",
        "target": TARGET_BACKEND,
        "method": "POST",
        "endpoint": "/images/{image_id}/analyze/tissue",
        "action": None,
        "route": None,
        "params": [_IMAGE_ID_PARAM],
        "keywords": ["mascara", "tissue", "fondo", "otsu"],
    },
    {
        "id": "generate-density-map",
        "name": "Generar mapa de densidades",
        "description": "Calcula el mapa de densidades de tejido por zonas.",
        "category": CATEGORY_ANALYSIS,
        "icon": "Grid3x3",
        "target": TARGET_BACKEND,
        "method": "POST",
        "endpoint": "/images/{image_id}/analyze/density",
        "action": None,
        "route": None,
        "params": [_IMAGE_ID_PARAM],
        "keywords": ["densidad", "heatmap", "mapa", "zonas"],
    },
    # --- Visualización (las gestiona la UI) --------------------------------
    {
        "id": "open-analytics-dashboard",
        "name": "Abrir dashboard de análisis",
        "description": "Muestra las gráficas y tablas interactivas de la imagen.",
        "category": CATEGORY_VISUALIZATION,
        "icon": "BarChart3",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "open-analytics",
        "route": None,
        "params": [],
        "keywords": ["graficas", "tablas", "dashboard", "analytics"],
    },
    {
        "id": "toggle-tissue-mask",
        "name": "Mostrar/ocultar máscara de tejido",
        "description": "Activa o desactiva la superposición de la máscara de tejido.",
        "category": CATEGORY_VISUALIZATION,
        "icon": "Layers",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "toggle-tissue-mask",
        "route": None,
        "params": [],
        "keywords": ["overlay", "mascara", "tejido"],
    },
    {
        "id": "toggle-density-map",
        "name": "Mostrar/ocultar mapa de densidades",
        "description": "Activa o desactiva la superposición del mapa de densidades.",
        "category": CATEGORY_VISUALIZATION,
        "icon": "Grid3x3",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "toggle-density-map",
        "route": None,
        "params": [],
        "keywords": ["overlay", "densidad", "heatmap"],
    },
    # --- Anotaciones (las gestiona la UI) ----------------------------------
    {
        "id": "export-coco",
        "name": "Exportar anotaciones (COCO)",
        "description": "Descarga las anotaciones de la imagen en formato COCO JSON.",
        "category": CATEGORY_ANNOTATIONS,
        "icon": "Download",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "export-coco",
        "route": None,
        "params": [],
        "keywords": ["exportar", "coco", "json", "descargar"],
    },
    {
        "id": "import-coco",
        "name": "Importar anotaciones (COCO)",
        "description": "Abre el asistente para importar anotaciones en formato COCO.",
        "category": CATEGORY_ANNOTATIONS,
        "icon": "Upload",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "import-coco",
        "route": None,
        "params": [],
        "keywords": ["importar", "coco", "json"],
    },
    {
        "id": "tool-select",
        "name": "Herramienta: seleccionar",
        "description": "Cambia a la herramienta de selección de anotaciones.",
        "category": CATEGORY_ANNOTATIONS,
        "icon": "MousePointer2",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "tool-select",
        "route": None,
        "params": [],
        "keywords": ["seleccionar", "cursor", "herramienta"],
    },
    {
        "id": "tool-rectangle",
        "name": "Herramienta: rectángulo",
        "description": "Cambia a la herramienta de dibujo de rectángulos.",
        "category": CATEGORY_ANNOTATIONS,
        "icon": "Square",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "tool-rectangle",
        "route": None,
        "params": [],
        "keywords": ["rectangulo", "caja", "dibujar"],
    },
    {
        "id": "tool-circle",
        "name": "Herramienta: círculo",
        "description": "Cambia a la herramienta de dibujo de círculos.",
        "category": CATEGORY_ANNOTATIONS,
        "icon": "Circle",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "tool-circle",
        "route": None,
        "params": [],
        "keywords": ["circulo", "elipse", "dibujar"],
    },
    {
        "id": "tool-polygon",
        "name": "Herramienta: polígono",
        "description": "Cambia a la herramienta de dibujo de polígonos.",
        "category": CATEGORY_ANNOTATIONS,
        "icon": "Pentagon",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "tool-polygon",
        "route": None,
        "params": [],
        "keywords": ["poligono", "forma", "dibujar"],
    },
    # --- Navegación (las gestiona la UI) -----------------------------------
    {
        "id": "go-gallery",
        "name": "Ir a la galería de imágenes",
        "description": "Navega al listado de imágenes.",
        "category": CATEGORY_NAVIGATION,
        "icon": "Images",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "navigate",
        "route": "/",
        "params": [],
        "keywords": ["galeria", "inicio", "listado", "imagenes"],
    },
    {
        "id": "go-upload",
        "name": "Subir nueva imagen",
        "description": "Navega a la página de subida de imágenes.",
        "category": CATEGORY_NAVIGATION,
        "icon": "UploadCloud",
        "target": TARGET_FRONTEND,
        "method": None,
        "endpoint": None,
        "action": "navigate",
        "route": "/upload",
        "params": [],
        "keywords": ["subir", "upload", "nueva", "imagen"],
    },
]

_COMMANDS_BY_ID: Dict[str, Dict[str, Any]] = {c["id"]: c for c in COMMANDS}


def _normalize(text: str) -> str:
    """Minúsculas sin acentos para una búsqueda tolerante."""
    text = text.lower()
    for a, b in (
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("ñ", "n"),
    ):
        text = text.replace(a, b)
    return text


def _matches(command: Dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        [
            command["name"],
            command["description"],
            command["category"],
            " ".join(command.get("keywords", [])),
        ]
    )
    return _normalize(query) in _normalize(haystack)


def list_commands(
    query: Optional[str] = None, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Devuelve los comandos, filtrados opcionalmente por texto y categoría."""
    result = COMMANDS
    if category:
        result = [c for c in result if c["category"] == category]
    if query and query.strip():
        result = [c for c in result if _matches(c, query.strip())]
    return list(result)


def list_categories() -> List[str]:
    """Categorías únicas en orden de aparición."""
    seen: List[str] = []
    for c in COMMANDS:
        if c["category"] not in seen:
            seen.append(c["category"])
    return seen


def get_command(command_id: str) -> Optional[Dict[str, Any]]:
    return _COMMANDS_BY_ID.get(command_id)
