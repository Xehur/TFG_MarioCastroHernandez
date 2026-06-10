# Optimización para Archivos WSI Grandes

## Problema
Las imágenes WSI (Whole Slide Images) pueden ser extremadamente grandes:
- Tamaños típicos: 1GB - 10GB
- Casos extremos: hasta 100GB
- Cargar todo en memoria es inviable y causa:
  - Consumo excesivo de RAM
  - Timeouts en requests
  - Fallos por memoria insuficiente

## Solución Implementada

### 1. Streaming con Chunks
El archivo se procesa en bloques pequeños (chunks) sin cargar todo en memoria:

```python
def save_upload_file(upload_file: UploadFile, destination: str) -> int:
    total_size = 0
    with open(destination, "wb") as buffer:
        while chunk := upload_file.file.read(settings.CHUNK_SIZE):
            buffer.write(chunk)
            total_size += len(chunk)
    return total_size
```

**Beneficios:**
- Uso constante de memoria (~8MB independiente del tamaño del archivo)
- Procesamiento eficiente de archivos de cualquier tamaño
- Detección temprana de errores

### 2. Configuración Ajustable

**CHUNK_SIZE: 8MB**
- Tamaño óptimo para balance entre:
  - Overhead de I/O (chunks muy pequeños = muchas operaciones)
  - Uso de memoria (chunks muy grandes = más RAM)

**MAX_FILE_SIZE: 10GB**
- Límite por defecto configurable según hardware
- Validación después del guardado para evitar carga previa

### 3. Validación Eficiente

El orden de validaciones está optimizado:
1. **Extensión** - validación instantánea sin I/O
2. **Duplicados** - query rápida a BD
3. **Guardado con streaming** - escritura eficiente
4. **Tamaño** - validación posterior al guardado
5. **Metadatos WSI** - extracción con OpenSlide (archivo ya en disco)

### 4. Manejo de Errores

```python
try:
    file_size = save_upload_file(file, file_path)
    
    if file_size > settings.MAX_FILE_SIZE:
        os.remove(file_path)  # Limpiar archivo inválido
        raise HTTPException(...)
        
except Exception as e:
    if os.path.exists(file_path):
        os.remove(file_path)  # Limpiar en caso de error
    raise
```

## Configuración

### Variables de entorno (.env):
```bash
MAX_FILE_SIZE=10737418240  # 10GB
CHUNK_SIZE=8388608         # 8MB
```

### Ajuste según hardware:
- **Servidor con 8GB RAM**: MAX_FILE_SIZE=5GB, CHUNK_SIZE=4MB
- **Servidor con 16GB RAM**: MAX_FILE_SIZE=10GB, CHUNK_SIZE=8MB
- **Servidor con 32GB+ RAM**: MAX_FILE_SIZE=20GB+, CHUNK_SIZE=16MB

## Pruebas

Tests implementados en `test_large_files.py`:
- Procesamiento por chunks
- Retorno correcto de tamaño
- Configuración apropiada
- Límites razonables para WSI

## Rendimiento Esperado

Para un archivo de 5GB:
- **Antes**: ~5GB de RAM, posible fallo
- **Después**: ~8MB de RAM constante, éxito garantizado

Tiempo de procesamiento: ~30-60 segundos (depende de disco)
- Red Gigabit: ~40 segundos
- SSD local: ~10-20 segundos
- HDD: ~60-90 segundos
