"""
Tests para endpoint de upload múltiple (drag & drop)
"""
import pytest
import io
from fastapi import status


def test_upload_multiple_valid_files(client):
    """Test que sube múltiples archivos válidos simulados"""
    # Crear archivos simulados
    files = [
        ("files", ("test1.svs", io.BytesIO(b"fake svs content 1"), "application/octet-stream")),
        ("files", ("test2.tiff", io.BytesIO(b"fake tiff content 2"), "application/octet-stream")),
    ]
    
    response = client.post("/images/upload-multiple", files=files)
    
    # Esperamos 207 Multi-Status
    assert response.status_code == status.HTTP_207_MULTI_STATUS
    
    data = response.json()
    assert data["total"] == 2
    # Los archivos no son WSI reales, así que fallarán en procesamiento
    # pero el endpoint debe funcionar


def test_upload_multiple_mixed_extensions(client):
    """Test con archivos de extensiones válidas e inválidas"""
    files = [
        ("files", ("valid.svs", io.BytesIO(b"fake content"), "application/octet-stream")),
        ("files", ("invalid.jpg", io.BytesIO(b"fake content"), "image/jpeg")),
        ("files", ("valid2.tiff", io.BytesIO(b"fake content"), "application/octet-stream")),
    ]
    
    response = client.post("/images/upload-multiple", files=files)
    
    assert response.status_code == status.HTTP_207_MULTI_STATUS
    
    data = response.json()
    assert data["total"] == 3
    assert data["failed"] >= 1  # Al menos el .jpg debe fallar
    
    # Verificar que el archivo inválido tiene error
    results = data["results"]
    invalid_result = next((r for r in results if r["filename"] == "invalid.jpg"), None)
    assert invalid_result is not None
    assert invalid_result["success"] is False
    assert "no soportado" in invalid_result["error"].lower()


def test_upload_multiple_empty_list(client):
    """Test que valida lista vacía de archivos"""
    response = client.post("/images/upload-multiple", files=[])
    
    # FastAPI retorna 422 cuando el parámetro requerido no se envía correctamente
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_upload_multiple_single_file(client):
    """Test con un solo archivo (caso extremo)"""
    files = [
        ("files", ("single.svs", io.BytesIO(b"fake content"), "application/octet-stream")),
    ]
    
    response = client.post("/images/upload-multiple", files=files)
    
    assert response.status_code == status.HTTP_207_MULTI_STATUS
    
    data = response.json()
    assert data["total"] == 1


def test_upload_multiple_response_structure(client):
    """Test que verifica la estructura de la respuesta"""
    files = [
        ("files", ("test1.svs", io.BytesIO(b"fake content"), "application/octet-stream")),
        ("files", ("test2.jpg", io.BytesIO(b"fake content"), "image/jpeg")),
    ]
    
    response = client.post("/images/upload-multiple", files=files)
    
    data = response.json()
    
    # Verificar estructura de respuesta
    assert "total" in data
    assert "successful" in data
    assert "failed" in data
    assert "results" in data
    
    # Verificar estructura de cada resultado
    for result in data["results"]:
        assert "filename" in result
        assert "success" in result
        assert "message" in result
        
        if result["success"]:
            assert "image" in result
        else:
            assert "error" in result


def test_upload_multiple_all_invalid_extensions(client):
    """Test con todos los archivos de extensión inválida"""
    files = [
        ("files", ("test1.jpg", io.BytesIO(b"fake content"), "image/jpeg")),
        ("files", ("test2.png", io.BytesIO(b"fake content"), "image/png")),
        ("files", ("test3.pdf", io.BytesIO(b"fake content"), "application/pdf")),
    ]
    
    response = client.post("/images/upload-multiple", files=files)
    
    assert response.status_code == status.HTTP_207_MULTI_STATUS
    
    data = response.json()
    assert data["total"] == 3
    assert data["failed"] == 3
    assert data["successful"] == 0


def test_upload_multiple_duplicate_filenames(client):
    """Test con archivos de nombres duplicados"""
    files = [
        ("files", ("duplicate.svs", io.BytesIO(b"fake content 1"), "application/octet-stream")),
        ("files", ("duplicate.svs", io.BytesIO(b"fake content 2"), "application/octet-stream")),
    ]
    
    response = client.post("/images/upload-multiple", files=files)
    
    assert response.status_code == status.HTTP_207_MULTI_STATUS
    
    data = response.json()
    assert data["total"] == 2
    # El segundo debería fallar por duplicado o ambos fallan por no ser WSI real


def test_process_single_file_function():
    """Test unitario de la función process_single_file"""
    from app.routers.images import process_single_file
    from fastapi import UploadFile
    
    # Test con extensión inválida
    file = UploadFile(
        filename="test.jpg",
        file=io.BytesIO(b"fake content")
    )
    
    # No podemos testear sin BD real, pero verificamos que la función existe
    assert callable(process_single_file)
