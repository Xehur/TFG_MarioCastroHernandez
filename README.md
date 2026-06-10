# TFG_MarioCastroHernández
Diseño y Desarrollo de un Sistema de Información web para la visualización  de imágenes WSI de biopsias de cáncer de mama con soporte de modelos de IA.

# Sistema de Visualización de Imágenes WSI con IA

##  Descripción

Aplicación full stack para la visualización de imágenes WSI (Whole Slide Images) de biopsias de cáncer de mama con soporte de modelos de inteligencia artificial.

## Stack Tecnológico

- **Frontend:** React + OpenSeadragon
- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **Imagen Processing:** OpenSlide
- **ML:** PyTorch
- **Deployment:** Docker + Docker Compose

## Requisitos Previos

- Docker y Docker Compose
- Python 3.9+
- Node.js 16+ (para frontend)
- Git

##  Instalación y Setup Local

### 1. Clonar repositorio

\`\`\`bash
git clone https://github.com/[usuario]/[repo].git
cd [repo]
git checkout develop
\`\`\`

### 2. Instalar pre-commit hooks

\`\`\`bash
pip install pre-commit
pre-commit install
\`\`\`

### 3. Setup del backend (en otra terminal)

\`\`\`bash
cd backend
pip install -r requirements.txt
python -m pytest
\`\`\`

##  Documentación
- [Arquitectura del Sistema](./docs/ARCHITECTURE.md)
- [Setup Detallado](./docs/SETUP.md)

##  Flujo de Trabajo

Este proyecto usa **Gitflow Workflow**. 

### Rama Principal

- `main`: Rama de producción
- `develop`: Rama de desarrollo

##  Features

- [ ] Visualización de imágenes WSI
- [ ] Sistema de anotaciones
- [ ] Análisis con IA
- [ ] Multi-imagen soporte
- [ ] Procesamiento paralelo

##  Testing

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
