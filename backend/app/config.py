"""
Configuración centralizada de la aplicación
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuración de la aplicación usando Pydantic Settings.
    Lee variables del archivo .env
    """

    # Información de la aplicación
    APP_NAME: str = "WSI Visualization API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "API para visualización de imágenes WSI con IA"

    # Ambiente
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Seguridad / Autenticación (JWT)
    SECRET_KEY: str = "CHANGE-ME-dev-secret-key-please-override-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas

    # Base de datos
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/wsi_db"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_NAME: str = "wsi_db"

    # CORS
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
    AI_DEVICE: str = "cpu"  # de momento solo "cpu" (ver Fase GPU AMD)
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

    class Config:
        env_file = ".env"
        case_sensitive = True

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