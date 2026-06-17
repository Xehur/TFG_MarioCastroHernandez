# Frontend - WSI Visualization System

Sistema de visualización de imágenes WSI (Whole Slide Images) construido con React y Vite.

## 🚀 Tecnologías

- **React 19** - Framework UI
- **Vite 8** - Build tool y dev server
- **React Router DOM** - Navegación
- **Axios** - Cliente HTTP
- **OpenSeadragon** - Visualizador de imágenes WSI
- **ESLint + Prettier** - Linting y formatting

## 📁 Estructura del Proyecto

```
src/
├── assets/          # Recursos estáticos (imágenes, estilos)
├── components/      # Componentes reutilizables
│   └── wsi/        # Componentes de visualización WSI
│       └── WSIViewer.jsx
├── config/          # Configuración de la aplicación
├── hooks/           # Custom React hooks
├── pages/           # Componentes de página
│   └── ImageViewer/ # Visualizador de imágenes WSI
├── services/        # Servicios de API
│   ├── api.js
│   └── imageService.js
└── utils/           # Funciones utilitarias
    └── helpers.js
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
- `GET /images/{id}/dzi.dzi` - Metadatos DZI para OpenSeadragon
- `GET /images/{id}/dzi_files/{level}/{col}_{row}.jpeg` - Tiles de imagen

## 🖼️ Visualizador WSI

### Uso del componente WSIViewer

```jsx
import { WSIViewer } from './components/wsi';
import config from './config/config';

function MyComponent() {
  const handleError = (error) => {
    console.error('Viewer error:', error);
  };

  return (
    <WSIViewer
      imageId={1}
      apiBaseUrl={config.apiBaseUrl}
      onError={handleError}
    />
  );
}
```

### Rutas disponibles

- `/` - Página de inicio
- `/viewer/:imageId` - Visualizador de imagen WSI

## 📦 Dependencias Principales

- `react` - ^19.2.6
- `react-dom` - ^19.2.6
- `react-router-dom` - ^7.6.2
- `axios` - ^1.9.0
- `openseadragon` - ^5.0.0
- `vite` - ^8.0.12

## 🎨 Code Style

Este proyecto usa:
- **ESLint** para linting de JavaScript/React
- **Prettier** para formateo de código

Configuración en:
- `eslint.config.js`
- `.prettierrc`

## 🧪 Testing

Para probar el visualizador WSI:

1. Asegúrate de que el backend esté corriendo en `http://localhost:8000`
2. Sube una imagen WSI usando el endpoint `/images/upload`
3. Navega a `/viewer/{imageId}` para visualizar la imagen

El visualizador incluye:
- ✅ Zoom y pan suaves
- ✅ Navegador miniatura
- ✅ Controles de navegación
- ✅ Carga progresiva de tiles
- ✅ Manejo de errores


