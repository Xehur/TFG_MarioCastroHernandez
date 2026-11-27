"""
Configuración centralizada de la aplicación
"""
import os
from pydantic import model_validator
from pydantic_settings import BaseSettings

# Valores por defecto SOLO válidos en desarrollo. En producción se rechazan.
_DEV_SECRET_KEY = "CHANGE-ME-dev-secret-key-please-override-in-env"
_INSECURE_DB_PASSWORDS = {"", "1234", "postgres", "password"}


class Settings(BaseSettings):
    """
    Configuración de la aplicación usando Pydantic Settings.
    Lee variables del archivo .env
    """

    # Información de la aplicación
    APP_NAME: str = "WSI Visualization API"
    APP_VERSION: str = "1.1.1"
    APP_DESCRIPTION: str = "API para visualización de imágenes WSI con IA"

    # Ambiente
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Seguridad / Autenticación (JWT)
    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas

    # Base de datos
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/wsi_db"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_NAME: str = "wsi_db"

    # Documentación interactiva (/docs, /redoc, /openapi.json). Si no se
    # define, se activa en desarrollo y se desactiva en producción.
    ENABLE_DOCS: bool | None = None

    # CORS. Desde variable de entorno se indica como JSON, p. ej.
    # CORS_ORIGINS='["https://mi-dominio.es"]'. En producción "*" no se admite.
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Uploads
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 1024 * 1024 * 1024 * 10  # 10GB por defecto
    CHUNK_SIZE: int = 1024 * 1024 * 8  # 8MB chunks para streaming

    # Clasificación IA (InceptionV3, tejido mamario BACH)
    # Ruta al checkpoint; por defecto <raíz del repo>/InceptionV3/HE_inceptionv3.pth
    INCEPTION_WEIGHTS_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "InceptionV3",
        "HE_inceptionv3.pth",
    )
    INCEPTION_WEIGHTS_SHA256: str = (
        "42515436dd2de4057eba0846aaac2561b38dc88efe960ef6a471807536394a5e"
    )
    # Dispositivo de la IA: "cpu", "cuda"/"gpu" (NVIDIA CUDA o AMD ROCm) o "auto".
    # Si se pide GPU y no está disponible, se usa CPU con un aviso en el log.
    AI_DEVICE: str = "cpu"
    # Campo de visión de cada parche, emulando las fotos de BACH
    # (2048x1536 px a ~0.42 µm/px ≈ 860x645 µm), reducido luego a 299x299.
    AI_FIELD_MPP: float = 0.42
    AI_FIELD_WIDTH_PX: int = 2048
    AI_FIELD_HEIGHT_PX: int = 1536
    # Máx. campos CON TEJIDO clasificados por análisis (~40 ms/campo en CPU).
    AI_MAX_PATCHES: int = 1000
    AI_MIN_TISSUE_FRAC: float = 0.35
    AI_BATCH_SIZE: int = 16
    AI_READ_WORKERS: int = 4  # hilos de lectura de campos de la WSI
    # Anotaciones: ventana deslizante con celdas más pequeñas que el campo para
    # localizar varios tipos de tejido dentro de la región (~celdas objetivo,
    # divisor máximo del campo y tope de campos clasificados).
    AI_ANNOTATION_TARGET_CELLS: int = 150
    AI_MAX_CELL_DIVISOR: int = 6
    AI_ANNOTATION_MAX_PATCHES: int = 300

    class Config:
        env_file = ".env"
        case_sensitive = True

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        """En producción, impide arrancar con la configuración insegura de
        desarrollo (clave JWT por defecto, contraseña de BD trivial, CORS *)."""
        if not self.is_production:
            return self
        errors = []
        if self.SECRET_KEY == _DEV_SECRET_KEY or len(self.SECRET_KEY) < 32:
            errors.append(
                "SECRET_KEY debe definirse con una cadena aleatoria de al menos 32 "
                "caracteres (p. ej. `python -c \"import secrets; "
                "print(secrets.token_urlsafe(48))\"`)"
            )
        if any(f":{pwd}@" in self.DATABASE_URL for pwd in _INSECURE_DB_PASSWORDS):
            errors.append("DATABASE_URL usa una contraseña de BD trivial")
        if "*" in self.CORS_ORIGINS:
            errors.append(
                "CORS_ORIGINS no puede ser '*': indica el origen del frontend"
            )
        if errors:
            raise ValueError(
                "Configuración insegura para ENVIRONMENT=production:\n- "
                + "\n- ".join(errors)
            )
        return self

    @property
    def docs_enabled(self) -> bool:
        """Swagger/ReDoc activos salvo que se desactiven (o en producción)."""
        if self.ENABLE_DOCS is not None:
            return self.ENABLE_DOCS
        return not self.is_production

    @property
    def is_production(self) -> bool:
        """Verificar si está en producción"""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Verificar si está en desarrollo"""
        return self.ENVIRONMENT == "development"


# Instancia global de configuración
settings = Settings()