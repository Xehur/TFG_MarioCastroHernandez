"""
Tests para endpoints de imágenes
"""
import pytest
import os
import io
from fastapi import status


def test_upload_image_invalid_extension(client):
    """Test que valida extensión de archivo inválida"""
    # Crear un archivo con extensión inválida
    file_content = b"fake image content"
    files = {
        "file": ("test.jpg", io.BytesIO(file_content), "image/jpeg")
    }
    
    response = client.post("/images/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no soportado" in response.json()["detail"].lower()


def test_upload_image_valid_extension_svs(client):
    """Test que valida extensión .svs válida"""
    # Crear un archivo mock con extensión válida
    # Nota: Este test fallará si intentamos procesarlo con OpenSlide
    # porque no es un archivo WSI real
    file_content = b"fake svs content"
    files = {
        "file": ("test.svs", io.BytesIO(file_content), "application/octet-stream")
    }
    
    response = client.post("/images/upload", files=files)
    
    # Esperamos 422 porque el archivo no es un WSI real
    assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_201_CREATED]


def test_upload_image_valid_extension_tiff(client):
    """Test que valida extensión .tiff válida"""
    file_content = b"fake tiff content"
    files = {
        "file": ("test.tiff", io.BytesIO(file_content), "application/octet-stream")
    }
    
    response = client.post("/images/upload", files=files)
    
    # Esperamos 422 porque el archivo no es un WSI real
    assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_201_CREATED]


def test_upload_image_valid_extension_mrxs(client):
    """Test que valida extensión .mrxs válida"""
    file_content = b"fake mrxs content"
    files = {
        "file": ("test.mrxs", io.BytesIO(file_content), "application/octet-stream")
    }
    
    response = client.post("/images/upload", files=files)
    
    # Esperamos 422 porque el archivo no es un WSI real
    assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_201_CREATED]


def test_list_images_empty(client):
    """Test que lista imágenes cuando no hay ninguna"""
    response = client.get("/images/")
    
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_list_images_with_pagination(client):
    """Test que lista imágenes con paginación"""
    response = client.get("/images/?skip=0&limit=10")
    
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_get_image_not_found(client):
    """Test que obtiene una imagen que no existe"""
    response = client.get("/images/99999")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "no encontrada" in response.json()["detail"].lower()


def test_delete_image_not_found(client):
    """Eliminar una imagen inexistente devuelve 404."""
    response = client.delete("/images/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_image_forbidden(client, test_db):
    """No se puede eliminar una imagen de otro usuario (403)."""
    from app.models.image import Image

    other = Image(
        filename="otheruser.svs",
        file_path="/tmp/otheruser.svs",
        user_id=99999,
        width=100,
        height=100,
        level_count=1,
        downsamples=[1.0],
        properties={},
        file_size_mb=1.0,
    )
    test_db.add(other)
    test_db.commit()
    test_db.refresh(other)

    response = client.delete(f"/images/{other.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_image_requires_auth(anon_client):
    """Eliminar una imagen requiere autenticación."""
    response = anon_client.delete("/images/1")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_upload_file_size_validation(client):
    """Test que valida el tamaño máximo de archivo"""
    # Crear un archivo muy grande (simular)
    # Nota: Este test es más conceptual ya que crear un archivo
    # realmente grande consumiría mucha memoria
    file_content = b"x" * 1024  # 1KB para el test
    files = {
        "file": ("large.svs", io.BytesIO(file_content), "application/octet-stream")
    }
    
    response = client.post("/images/upload", files=files)
    
    # El archivo es pequeño, así que debería pasar la validación de tamaño
    # pero fallar en el procesamiento WSI
    assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE]


def test_validation_functions():
    """Test de funciones de validación"""
    from app.routers.images import validate_file_extension
    
    # Extensiones válidas
    assert validate_file_extension("test.svs") == True
    assert validate_file_extension("test.tiff") == True
    assert validate_file_extension("test.tif") == True
    assert validate_file_extension("test.mrxs") == True
    
    # Extensiones válidas con mayúsculas
    assert validate_file_extension("test.SVS") == True
    assert validate_file_extension("test.TIFF") == True
    
    # Extensiones inválidas
    assert validate_file_extension("test.jpg") == False
    assert validate_file_extension("test.png") == False
    assert validate_file_extension("test.pdf") == False
    assert validate_file_extension("test.txt") == False
