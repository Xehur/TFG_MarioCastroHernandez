"""
Tests de ejemplo usando fixtures del conftest
"""
import pytest


@pytest.mark.unit
def test_example_with_mock_file(mock_svs_file):
    """Ejemplo de test usando fixture de archivo mock"""
    assert mock_svs_file.filename == "test.svs"
    assert mock_svs_file.file.read() == b"fake svs content"


@pytest.mark.unit
def test_example_with_metadata(sample_image_metadata):
    """Ejemplo de test usando fixture de metadatos"""
    assert sample_image_metadata["filename"] == "test.svs"
    assert sample_image_metadata["level_count"] == 3
    assert sample_image_metadata["width"] == 35868


@pytest.mark.integration
def test_example_with_client(client):
    """Ejemplo de test de integración con cliente API"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


@pytest.mark.unit
def test_example_with_multiple_fixtures(mock_svs_file, mock_tiff_file, sample_image_metadata):
    """Ejemplo usando múltiples fixtures"""
    assert mock_svs_file.filename.endswith(".svs")
    assert mock_tiff_file.filename.endswith(".tiff")
    assert "width" in sample_image_metadata
