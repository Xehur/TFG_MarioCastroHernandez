"""
Router para manejo de imágenes WSI
"""
import os
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.image import Image
from app.schemas.image import ImageResponse
from app.services.wsi.openslide_service import OpenSlideService

router = APIRouter(
    prefix="/images",
    tags=["images"]
)

logger = logging.getLogger(__name__)

# Formatos permitidos
ALLOWED_EXTENSIONS = {".svs", ".tiff", ".tif", ".mrxs"}


def get_db():
    """Dependencia para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_file_extension(filename: str) -> bool:
    """
    Valida que la extensión del archivo sea permitida
    
    Args:
        filename: Nombre del archivo
        
    Returns:
        True si es válido, False en caso contrario
    """
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


def save_upload_file(upload_file: UploadFile, destination: str) -> int:
    """
    Guarda un archivo subido en el destino especificado usando streaming
    para evitar cargar todo el archivo en memoria.
    
    Args:
        upload_file: Archivo subido
        destination: Ruta de destino
        
    Returns:
        Tamaño del archivo en bytes
    """
    try:
        total_size = 0
        with open(destination, "wb") as buffer:
            # Procesar el archivo por chunks
            while chunk := upload_file.file.read(settings.CHUNK_SIZE):
                buffer.write(chunk)
                total_size += len(chunk)
        return total_size
    except Exception as e:
        logger.error(f"Error guardando archivo: {e}")
        # Limpiar archivo parcial si hay error
        if os.path.exists(destination):
            os.remove(destination)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando archivo: {str(e)}"
        )
    finally:
        upload_file.file.close()


@router.post("/upload", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    user_id: int = 1,  # Por ahora hardcodeado, luego vendrá del auth
    db: Session = Depends(get_db)
):
    """
    Sube una imagen WSI al servidor
    
    Args:
        file: Archivo a subir
        user_id: ID del usuario (temporal)
        db: Sesión de base de datos
        
    Returns:
        Información de la imagen subida
    """
    # Validar extensión
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Verificar si ya existe
    existing_image = db.query(Image).filter(Image.filename == file.filename).first()
    if existing_image:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Archivo {file.filename} ya existe"
        )
    
    # Crear directorio de uploads si no existe
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Guardar archivo con streaming (devuelve el tamaño)
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    file_size = save_upload_file(file, file_path)
    
    # Validar tamaño después de guardarlo
    if file_size > settings.MAX_FILE_SIZE:
        # Eliminar archivo si excede el límite
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archivo demasiado grande. Máximo: {settings.MAX_FILE_SIZE / (1024*1024*1024):.1f}GB"
        )
    
    logger.info(f"Archivo guardado: {file_path} ({file_size / (1024*1024):.2f}MB)")
    
    # Extraer metadatos con OpenSlide
    try:
        slide_service = OpenSlideService(file_path)
        metadata = slide_service.get_metadata()
        width, height = metadata['dimensions']
        
        # Crear registro en BD
        db_image = Image(
            filename=file.filename,
            file_path=file_path,
            user_id=user_id,
            width=width,
            height=height,
            level_count=metadata['level_count'],
            downsamples=metadata['downsamples'],
            properties=metadata['properties'],
            file_size_mb=round(file_size / (1024 * 1024), 2)
        )
        
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        
        slide_service.close()
        
        logger.info(f"Imagen registrada en BD: {db_image.id}")
        
        return db_image
        
    except Exception as e:
        # Si falla la extracción de metadatos, eliminar archivo
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Error procesando imagen: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error procesando imagen WSI: {str(e)}"
        )


@router.get("/", response_model=List[ImageResponse])
async def list_images(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lista todas las imágenes subidas
    
    Args:
        skip: Número de registros a saltar (paginación)
        limit: Número máximo de registros a retornar
        db: Sesión de base de datos
        
    Returns:
        Lista de imágenes
    """
    images = db.query(Image).offset(skip).limit(limit).all()
    return images


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene información de una imagen específica
    
    Args:
        image_id: ID de la imagen
        db: Sesión de base de datos
        
    Returns:
        Información de la imagen
    """
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imagen con ID {image_id} no encontrada"
        )
    return image
