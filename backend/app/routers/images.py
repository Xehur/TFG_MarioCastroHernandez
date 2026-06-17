"""
Router para manejo de imágenes WSI
"""
import os
import logging
import io
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from PIL import Image as PILImage

from app.config import settings
from app.db import SessionLocal
from app.models.image import Image
from app.schemas.image import ImageResponse, ImageUploadResult, MultipleUploadResponse
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
    para evitar cargar el archivo en memoria.
    
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


def process_single_file(file: UploadFile, user_id: int, db: Session) -> ImageUploadResult:
    """
    Procesa un archivo individual y retorna el resultado
    
    Args:
        file: Archivo a procesar
        user_id: ID del usuario
        db: Sesión de base de datos
        
    Returns:
        Resultado del procesamiento
    """
    try:
        # Validar extensión
        if not validate_file_extension(file.filename):
            return ImageUploadResult(
                filename=file.filename,
                success=False,
                message="Formato no soportado",
                error=f"Formato no soportado. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Verificar si ya existe
        existing_image = db.query(Image).filter(Image.filename == file.filename).first()
        if existing_image:
            return ImageUploadResult(
                filename=file.filename,
                success=False,
                message="Archivo ya existe",
                error=f"Archivo {file.filename} ya existe en el sistema"
            )
        
        # Crear directorio de uploads si no existe
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        # Guardar archivo con streaming
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        file_size = save_upload_file(file, file_path)
        
        # Validar tamaño
        if file_size > settings.MAX_FILE_SIZE:
            if os.path.exists(file_path):
                os.remove(file_path)
            return ImageUploadResult(
                filename=file.filename,
                success=False,
                message="Archivo demasiado grande",
                error=f"Archivo demasiado grande. Máximo: {settings.MAX_FILE_SIZE / (1024*1024*1024):.1f}GB"
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
            
            return ImageUploadResult(
                filename=file.filename,
                success=True,
                message="Archivo procesado exitosamente",
                image=ImageResponse.model_validate(db_image)
            )
            
        except Exception as e:
            # Si falla la extracción de metadatos, eliminar archivo
            if os.path.exists(file_path):
                os.remove(file_path)
            logger.error(f"Error procesando imagen {file.filename}: {e}")
            return ImageUploadResult(
                filename=file.filename,
                success=False,
                message="Error procesando imagen WSI",
                error=f"Error procesando imagen WSI: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error inesperado procesando {file.filename}: {e}")
        return ImageUploadResult(
            filename=file.filename,
            success=False,
            message="Error inesperado",
            error=f"Error inesperado: {str(e)}"
        )


@router.post("/upload-multiple", response_model=MultipleUploadResponse, status_code=status.HTTP_207_MULTI_STATUS)
async def upload_multiple_images(
    files: List[UploadFile] = File(...),
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Sube múltiples imágenes WSI al servidor (soporte para drag & drop)
    
    Args:
        files: Lista de archivos a subir
        user_id: ID del usuario (temporal)
        db: Sesión de base de datos
        
    Returns:
        Resultado del procesamiento de cada archivo
        
    Status Code:
        207 Multi-Status: Algunos archivos pueden tener éxito y otros fallar
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron archivos"
        )
    
    logger.info(f"Procesando {len(files)} archivos")
    
    results = []
    successful = 0
    failed = 0
    
    # Procesar cada archivo
    for file in files:
        logger.info(f"Procesando archivo: {file.filename}")
        result = process_single_file(file, user_id, db)
        results.append(result)
        
        if result.success:
            successful += 1
        else:
            failed += 1
    
    logger.info(f"Procesamiento completo: {successful} exitosos, {failed} fallidos")
    
    return MultipleUploadResponse(
        total=len(files),
        successful=successful,
        failed=failed,
        results=results
    )


@router.get("/{image_id}/dzi.dzi")
async def get_dzi_metadata(
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene el archivo DZI (Deep Zoom Image) con metadatos para OpenSeadragon
    
    Args:
        image_id: ID de la imagen
        db: Sesión de base de datos
        
    Returns:
        XML con configuración DZI
    """
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imagen con ID {image_id} no encontrada"
        )
    
    # Verificar que el archivo existe
    if not os.path.exists(image.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo de imagen no encontrado"
        )
    
    # Tamaño del tile (estándar para OpenSeadragon)
    tile_size = 256
    overlap = 0
    
    # Formato DZI XML
    dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       Format="jpeg"
       Overlap="{overlap}"
       TileSize="{tile_size}">
    <Size Width="{image.width}" Height="{image.height}"/>
</Image>'''
    
    return Response(content=dzi_xml, media_type="application/xml")


@router.get("/{image_id}/dzi_files/{level}/{col}_{row}.jpeg")
async def get_tile(
    image_id: int,
    level: int,
    col: int,
    row: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un tile específico de la imagen WSI para OpenSeadragon
    
    Args:
        image_id: ID de la imagen
        level: Nivel de zoom (0 = más zoom out, mayor número = más zoom in)
        col: Columna del tile
        row: Fila del tile
        db: Sesión de base de datos
        
    Returns:
        Imagen JPEG del tile
    """
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imagen con ID {image_id} no encontrada"
        )
    
    if not os.path.exists(image.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo de imagen no encontrado"
        )
    
    try:
        slide_service = OpenSlideService(image.file_path)
        
        # OpenSeadragon usa niveles invertidos: 0 es el más bajo
        # OpenSlide usa: 0 es el más alto
        # Convertir nivel DZI a nivel OpenSlide
        openslide_level = image.level_count - 1 - level
        
        # Asegurar que el nivel es válido
        if openslide_level < 0:
            openslide_level = 0
        elif openslide_level >= image.level_count:
            openslide_level = image.level_count - 1
        
        tile_size = 256
        
        # Calcular coordenadas en el nivel base (nivel 0 de OpenSlide)
        downsample = slide_service.get_downsamples()[openslide_level]
        x = int(col * tile_size * downsample)
        y = int(row * tile_size * downsample)
        
        # Extraer tile
        region = slide_service.extract_tile(x, y, openslide_level, tile_size)
        
        # Convertir RGBA a RGB
        if region.mode == 'RGBA':
            rgb_region = PILImage.new('RGB', region.size, (255, 255, 255))
            rgb_region.paste(region, mask=region.split()[3])
            region = rgb_region
        
        # Convertir a JPEG
        img_byte_arr = io.BytesIO()
        region.save(img_byte_arr, format='JPEG', quality=85)
        img_byte_arr.seek(0)
        
        slide_service.close()
        
        return StreamingResponse(img_byte_arr, media_type="image/jpeg")
        
    except ValueError as e:
        logger.error(f"Error de valor al obtener tile: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error obteniendo tile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo tile: {str(e)}"
        )
