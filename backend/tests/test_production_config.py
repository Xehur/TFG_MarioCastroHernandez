"""Validación de la configuración en ENVIRONMENT=production."""
import pytest

from app.config import Settings

STRONG_KEY = "x" * 48
SAFE_DB = "postgresql://postgres:s3cr3t-pass@db:5432/wsi_db"


def _prod(**overrides):
    values = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": STRONG_KEY,
        "DATABASE_URL": SAFE_DB,
        "CORS_ORIGINS": ["https://wsi.example.org"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_with_safe_config_starts():
    settings = _prod()
    assert settings.is_production
    assert settings.docs_enabled is False


def test_production_rejects_default_secret_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _prod(SECRET_KEY="CHANGE-ME-dev-secret-key-please-override-in-env")


def test_production_rejects_short_secret_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _prod(SECRET_KEY="corta")


def test_production_rejects_trivial_db_password():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _prod(DATABASE_URL="postgresql://postgres:1234@db:5432/wsi_db")


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _prod(CORS_ORIGINS=["*"])


def test_docs_can_be_enabled_explicitly_in_production():
    assert _prod(ENABLE_DOCS=True).docs_enabled is True


def test_development_keeps_permissive_defaults():
    settings = Settings(_env_file=None, ENVIRONMENT="development")
    assert settings.docs_enabled is True
    assert settings.CORS_ORIGINS == ["*"]
