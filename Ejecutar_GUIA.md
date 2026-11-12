# Cómo levantar el proyecto

Guía rápida para arrancar el **backend** (FastAPI) y el **frontend** (React + Vite)
y probar la aplicación en local.

## Requisitos previos

- Python 3.12 con las dependencias del backend instaladas
- Node.js con las dependencias del frontend instaladas (`npm install` dentro de `frontend/`)
- En PowerShell, usa `npm.cmd` / `npx.cmd` (no `npm` / `npx`) por la política de ejecución de scripts

---

## 1. Backend (puerto 8000)

Abre una terminal:
pip install -r requirements.txt (SETUP)
```powershell
cd C:\Users\pocom\Projecto_TFG\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs

### Modelo de IA (InceptionV3)

La clasificación de tejido usa el checkpoint `InceptionV3/HE_inceptionv3.pth`
(no se versiona en Git). Por defecto se busca en esa ruta de la raíz del repo;
para usar otra, define `INCEPTION_WEIGHTS_PATH` en `backend/.env` o en el
entorno. Para comprobar que carga y funciona en CPU:

```powershell
cd C:\Users\pocom\Projecto_TFG\backend
python scripts\smoke_inception.py
# Opcional, con fotos BACH etiquetadas en subcarpetas Benign/InSitu/Invasive/Normal:
python scripts\smoke_inception.py --images C:\ruta\BACH\Photos --limit 25
```

Si el checkpoint falta, los endpoints de IA responden 503 y el resto de la
aplicación funciona con normalidad.

---

## 2. Frontend (puerto 5175)

Abre **otra** terminal (deja el backend corriendo en la anterior):

```powershell
cd C:\Users\pocom\Projecto_TFG\frontend
npm.cmd run dev -- --port 5175
```

- Aplicación: http://localhost:5175

> Nota: el frontend lee la URL del backend desde `frontend/.env`
> (`VITE_API_BASE_URL=http://localhost:8000`). Si cambias ese archivo,
> reinicia el servidor de Vite para que lo tome.

---

## 3. Probar la aplicación

1. Abre http://localhost:5175 en el navegador.
2. **Ver imágenes** (`/`): galería con las imágenes subidas.
3. **Subir** (`/upload`): arrastra y suelta una imagen WSI (.svs, .tiff, .tif, .mrxs).
4. **Visualizar** (`/viewer/:id`): zoom, pan, fullscreen y navegación por niveles.

Si recargas tras un cambio de código, fuerza la recarga con **Ctrl + Shift + R**.

---

## 4. Comprobaciones rápidas (opcional)

```powershell
# ¿Responde el backend?
curl.exe -s -o NUL -w "backend: %{http_code}\n" "http://localhost:8000/images/?limit=1"

# ¿Responde el frontend?
curl.exe -s -o NUL -w "frontend: %{http_code}\n" "http://localhost:5175/"
```

Ambos deben devolver `200`.

---

## 5. Tests (opcional)

```powershell
# Tests del backend
cd C:\Users\pocom\Projecto_TFG\backend
python -m pytest -q

# Lint y build del frontend
cd C:\Users\pocom\Projecto_TFG\frontend
npm.cmd run lint
npm.cmd run build
```

---

## 6. Parar los servidores

En cada terminal, pulsa **Ctrl + C**.
