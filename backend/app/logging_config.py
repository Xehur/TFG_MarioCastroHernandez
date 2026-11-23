"""
Configuración de logging para la aplicación
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings


def setup_logging():
    """
    Configura el sistema de logging de la aplicación
    """

    # Crear directorio de logs si no existe
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Formato de logs
    log_format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)
    console_formatter = logging.Formatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Handler para archivo (rotativo)
    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(settings.LOG_LEVEL)
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Logger específico para la aplicación
    app_logger = logging.getLogger("app")
    app_logger.setLevel(settings.LOG_LEVEL)

    return app_logger


# Logger global
logger = setup_logging()