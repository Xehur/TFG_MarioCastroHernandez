# Documentación de Testing

## Estructura de Tests

```
tests/
├── __init__.py                    # Módulo principal de tests
├── conftest.py                    # Fixtures globales de pytest
├── unit/                          # Tests unitarios
│   └── __init__.py
├── integration/                   # Tests de integración
│   └── __init__.py
├── test_health.py                 # Tests de endpoints de salud
├── test_users.py                  # Tests de usuarios
├── test_images.py                 # Tests de upload individual
├── test_large_files.py            # Tests de archivos grandes
├── test_multiple_upload.py        # Tests de upload múltiple
└── test_openslide_service.py      # Tests del servicio OpenSlide
```

## Configuración (pytest.ini)

El archivo `pytest.ini` contiene la configuración global de pytest:
- Directorio de tests: `tests/`
- Patrones de archivos: `test_*.py`
- Markers personalizados para categorizar tests
- Opciones por defecto: verbose, colores, manejo de warnings

## Fixtures Disponibles (conftest.py)

### Fixtures de Base de Datos

**`db_setup`**
- Scope: function
- Crea una BD SQLite temporal para cada test
- Se limpia automáticamente después del test

**`test_db`**
- Proporciona una sesión de BD directa
- Útil para tests que necesitan manipular datos

### Fixtures de Cliente API

**`client`**
- Proporciona un TestClient de FastAPI
- Configurado con la BD de test
- Listo para hacer requests HTTP a los endpoints

### Fixtures de Archivos Mock

**`mock_svs_file`**
- Archivo .svs simulado para tests
- No requiere archivo WSI real

**`mock_tiff_file`**
- Archivo .tiff simulado para tests

**`mock_invalid_file`**
- Archivo con extensión inválida (.jpg)
- Para tests de validación

**`mock_large_file`**
- Archivo grande simulado (10MB)
- Para tests de archivos grandes

### Fixtures de Datos

**`sample_image_metadata`**
- Metadatos de ejemplo de una imagen WSI
- Útil para tests que necesitan datos de prueba

### Fixtures de Limpieza

**`cleanup_uploads`**
- Autouse: Se ejecuta automáticamente
- Limpia archivos de test del directorio uploads
- Previene contaminación entre tests

## Ejecutar Tests

### Todos los tests
```powershell
pytest
```

### Tests específicos
```powershell
pytest tests/test_images.py
pytest tests/test_images.py::test_upload_image_invalid_extension
```

### Con verbose
```powershell
pytest -v
```

### Con cobertura (si tienes pytest-cov)
```powershell
pytest --cov=app --cov-report=html
```

### Por markers
```powershell
pytest -m unit          # Solo tests unitarios
pytest -m integration   # Solo tests de integración
pytest -m "not slow"    # Excluir tests lentos
```

## Markers Disponibles

- `@pytest.mark.unit` - Tests unitarios
- `@pytest.mark.integration` - Tests de integración
- `@pytest.mark.slow` - Tests que tardan más
- `@pytest.mark.wsi` - Tests que requieren archivos WSI reales
- `@pytest.mark.upload` - Tests de upload

## Ejemplo de Uso de Fixtures

```python
def test_upload_with_mock(client, mock_svs_file):
    """Test usando fixtures de cliente y archivo mock"""
    files = {"file": (mock_svs_file.filename, mock_svs_file.file)}
    response = client.post("/images/upload", files=files)
    # Assertions...

def test_with_db(test_db, sample_image_metadata):
    """Test usando fixture de BD y metadatos"""
    from app.models.image import Image
    
    image = Image(**sample_image_metadata)
    test_db.add(image)
    test_db.commit()
    # Assertions...
```

## Buenas Prácticas

1. **Usa fixtures** en lugar de crear datos manualmente
2. **Marca tus tests** con decoradores apropiados
3. **Limpia después** - usa fixtures autouse para cleanup
4. **Tests independientes** - cada test debe poder ejecutarse solo
5. **Nombres descriptivos** - `test_upload_invalid_extension` es mejor que `test1`
6. **Documenta** - usa docstrings para explicar qué prueba cada test

## Base de Datos de Test

Los tests usan SQLite en lugar de PostgreSQL para:
- Mayor velocidad
- No requiere servidor externo
- Fácil de limpiar entre tests
- Ideal para CI/CD

La BD de test se crea en `test.db` y se elimina después de los tests.

## Cobertura de Tests Actual

- **Total**: 21 tests
- **Pasando**: 21/21 (100%)
- **Categorías**:
  - Health endpoints: 5 tests
  - Usuarios: 5 tests
  - Upload individual: 9 tests
  - Archivos grandes: 4 tests
  - Upload múltiple: 8 tests
  - OpenSlide service: 3 tests

## Integración Continua

Los tests están configurados para ejecutarse en CI/CD con GitHub Actions.
Ver `.github/workflows/` para la configuración de workflows.

## Troubleshooting

**Error: ModuleNotFoundError**
- Asegúrate de estar en el directorio `backend/`
- Ejecuta: `pip install -r requirements.txt`

**Error: Database locked**
- Cierra cualquier conexión activa a test.db
- Elimina test.db manualmente si persiste

**Tests fallan por archivos WSI**
- Los tests usan archivos mock, no requieren WSI reales
- Si ves errores de OpenSlide, verifica la instalación de openslide-bin

**Fixtures no encontradas**
- Verifica que conftest.py esté en el directorio tests/
- No importes fixtures, pytest las descubre automáticamente
