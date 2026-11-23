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

class _FakeOpenSlide:
    """Slide mínimo con pirámide de 3 niveles (1x, 4x, 16x) de 40000x30000."""

    dimensions = (40000, 30000)
    level_downsamples = (1.0, 4.0, 16.0)

    def __init__(self):
        self.calls = []

    def read_region(self, location, level, size):
        from PIL import Image
        self.calls.append((location, level, size))
        return Image.new("RGBA", size, (200, 100, 150, 255))


def _service_with_fake():
    service = OpenSlideService.__new__(OpenSlideService)
    service.slide = _FakeOpenSlide()
    return service


def test_read_field_rgb_rectangular_elige_nivel():
    service = _service_with_fake()
    # Campo BACH a 0.25 MPP: 3441x2580 px nivel 0 -> salida 399x299.
    arr = service.read_field_rgb(10000, 10000, 3441, 2580, 399, 299)
    assert arr.shape == (299, 399, 3)
    (x, y), level, size = service.slide.calls[0]
    assert level == 1  # ds=4 <= 3441/399≈8.6 ; ds=16 lo sobre-reduciría
    assert size == (860, 645)
    assert (x, y) == (10000 - 1720, 10000 - 1290)


def test_read_field_rgb_se_mantiene_dentro_de_la_imagen():
    service = _service_with_fake()
    service.read_field_rgb(39990, 5, 2000, 1500, 400, 300)
    (x, y), _, _ = service.slide.calls[0]
    assert x == 40000 - 2000 and y == 0


def test_read_patch_rgb_sigue_siendo_cuadrado():
    service = _service_with_fake()
    arr = service.read_patch_rgb(5000, 5000, 448, out_size=224)
    assert arr.shape == (224, 224, 3)
