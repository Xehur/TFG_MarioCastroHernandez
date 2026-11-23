# Imagen del frontend: build con Vite y servido por Nginx
FROM node:22-alpine AS build

WORKDIR /app

# Instala dependencias primero (aprovecha la caché de capas)
COPY frontend/package*.json ./
RUN npm install

# Copia el resto del código del frontend
COPY frontend/ ./

# URL del backend embebida en el build (Vite la resuelve en tiempo de compilación).
# El navegador la usará, por lo que debe ser accesible desde la máquina del usuario.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ENV=production

RUN npm run build

# --- Fase de servidor estático ---
FROM nginx:alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
