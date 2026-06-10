"""
Tests para procesamiento eficiente de archivos grandes
"""
import pytest
import os
import io
from app.routers.images import save_upload_file
from app.config import settings
from fastapi import UploadFile


def test_save_upload_file_streaming():
    """Test que verifica que save_upload_file procesa archivos por chunks"""
    # Crear un archivo simulado de 10MB
    file_size = 10 * 1024 * 1024  # 10MB
    file_content = b"x" * file_size
    
    # Crear un UploadFile mock
    file = UploadFile(
        filename="test_large.svs",
        file=io.BytesIO(file_content)
    )
    
    destination = os.path.join(settings.UPLOAD_DIR, "test_large_temp.svs")
    
    try:
        # Guardar archivo
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        saved_size = save_upload_file(file, destination)
        
        # Verificar que el tamaño es correcto
        assert saved_size == file_size
        
        # Verificar que el archivo existe
        assert os.path.exists(destination)
        
        # Verificar el tamaño del archivo en disco
        assert os.path.getsize(destination) == file_size
        
    finally:
        # Limpiar
        if os.path.exists(destination):
            os.remove(destination)


def test_save_upload_file_returns_size():
    """Test que verifica que save_upload_file retorna el tamaño correcto"""
    file_content = b"test content"
    file = UploadFile(
        filename="test_size.svs",
        file=io.BytesIO(file_content)
    )
    
    destination = os.path.join(settings.UPLOAD_DIR, "test_size_temp.svs")
    
    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        saved_size = save_upload_file(file, destination)
        
        assert saved_size == len(file_content)
        
    finally:
        if os.path.exists(destination):
            os.remove(destination)


def test_chunk_size_configuration():
    """Test que verifica que CHUNK_SIZE está configurado apropiadamente"""
    # Verificar que el chunk size es razonable (entre 1MB y 100MB)
    assert settings.CHUNK_SIZE >= 1024 * 1024  # Al menos 1MB
    assert settings.CHUNK_SIZE <= 100 * 1024 * 1024  # Máximo 100MB
    
    # Verificar que es múltiplo de 1MB para eficiencia
    assert settings.CHUNK_SIZE % (1024 * 1024) == 0


def test_max_file_size_for_wsi():
    """Test que verifica que MAX_FILE_SIZE es apropiado para WSI"""
    # Las imágenes WSI pueden ser muy grandes (varios GB)
    # Verificar que el límite es al menos 1GB
    min_size = 1 * 1024 * 1024 * 1024  # 1GB
    assert settings.MAX_FILE_SIZE >= min_size, \
        f"MAX_FILE_SIZE ({settings.MAX_FILE_SIZE / (1024**3):.1f}GB) debe ser al menos 1GB para imágenes WSI"
