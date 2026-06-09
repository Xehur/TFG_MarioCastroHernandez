import pytest
import os
from app.services.wsi.openslide_service import OpenSlideService


class TestOpenSlideService:

    def test_validate_format_valid(self):
        """Test que acepta formatos válidos."""
        # Solo validamos que no lanza error
        service = OpenSlideService.__new__(OpenSlideService)
        service.file_path = "test.svs"
        service._validate_format()  # No debe lanzar error

    def test_validate_format_invalid(self):
        """Test que rechaza formatos inválidos."""
        service = OpenSlideService.__new__(OpenSlideService)
        service.file_path = "test.jpg"
        with pytest.raises(ValueError):
            service._validate_format()

    def test_supported_formats(self):
        """Test que los formatos soportados son correctos."""
        expected = {'.svs', '.tiff', '.tif', '.mrxs'}
        assert OpenSlideService.SUPPORTED_FORMATS == expected