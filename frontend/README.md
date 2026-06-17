# Frontend - WSI Visualization System

Sistema de visualización de imágenes WSI (Whole Slide Images) construido con React y Vite.

## 🚀 Tecnologías

- **React 19** - Framework UI
- **Vite 8** - Build tool y dev server
- **React Router DOM** - Navegación
- **Axios** - Cliente HTTP
- **ESLint + Prettier** - Linting y formatting

## 📁 Estructura del Proyecto

```
src/
├── assets/          # Recursos estáticos (imágenes, estilos)
├── components/      # Componentes reutilizables
├── config/          # Configuración de la aplicación
├── hooks/           # Custom React hooks
├── pages/           # Componentes de página
├── services/        # Servicios de API
└── utils/           # Funciones utilitarias
```

## 🛠️ Setup

### Instalar dependencias

```bash
npm install
```

### Variables de entorno

Copiar `.env.example` a `.env` y configurar:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_ENV=development
```

## 📜 Scripts Disponibles

```bash
# Desarrollo
npm run dev              # Inicia servidor de desarrollo (http://localhost:5173)

# Build
npm run build            # Construye para producción

# Linting y Formatting
npm run lint             # Ejecuta ESLint
npm run lint:fix         # Fix automático de ESLint
npm run format           # Formatea código con Prettier
npm run format:check     # Verifica formato sin modificar

# Preview
npm run preview          # Preview de build de producción
```

## 🔗 Backend API

El frontend se conecta al backend FastAPI en `http://localhost:8000`

Endpoints disponibles:
- `GET /images/` - Lista de imágenes
- `GET /images/{id}` - Imagen específica
- `POST /images/upload` - Subir imagen
- `POST /images/upload-multiple` - Subir múltiples imágenes

## 📦 Dependencias Principales

- `react` - ^19.2.6
- `react-dom` - ^19.2.6
- `react-router-dom` - ^7.6.2
- `axios` - ^1.9.0
- `vite` - ^8.0.12

## 🎨 Code Style

Este proyecto usa:
- **ESLint** para linting de JavaScript/React
- **Prettier** para formateo de código

Configuración en:
- `eslint.config.js`
- `.prettierrc`

