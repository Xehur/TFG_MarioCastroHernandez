"""
Router para manejo de imágenes WSI
"""
import os
import logging
import io
import shutil
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from PIL import Image as PILImage

from app.config import settings
from app.db import SessionLocal
from app.models.image import Image
from app.models.user import User
from app.models.annotation import Annotation
from app.schemas.image import ImageResponse, ImageUploadResult, MultipleUploadResponse
from app.services.wsi.openslide_service import OpenSlideService
from app.services.wsi.slide_cache import slide_cache
from app.core.deps import get_current_user

router = APIRouter(
    prefix="/images",
    tags=["images"]
)

logger = logging.getLogger(__name__)

# Formatos permitidos
ALLOWED_EXTENSIONS = {".svs", ".tiff", ".tif", ".mrxs"}


def user_upload_path(user_id: int, filename: str) -> str:
    """Ruta de guardado de una WSI: ``<UPLOAD_DIR>/<user_id>/<nombre>``.

    Cada usuario tiene su propia carpeta, de modo que dos usuarios pueden subir
    un archivo con el mismo nombre sin sobrescribirse.
    """
    user_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, os.path.basename(filename))


def find_user_image(db: Session, user_id: int, filename: str):
    """Imagen del usuario con ese nombre (los duplicados se miden por usuario)."""
    return (
        db.query(Image)
        .filter(Image.user_id == user_id, Image.filename == filename)
        .first()
    )


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sube una imagen WSI al servidor

    Args:
        file: Archivo a subir
        db: Sesión de base de datos
        current_user: Usuario autenticado (propietario de la imagen)

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
    existing_image = find_user_image(db, current_user.id, file.filename)
    if existing_image:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Archivo {file.filename} ya existe"
        )
    
    # Guardar archivo con streaming (devuelve el tamaño), en la carpeta del usuario
    file_path = user_upload_path(current_user.id, file.filename)
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
            user_id=current_user.id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista las imágenes subidas por el usuario autenticado

    Args:
        skip: Número de registros a saltar (paginación)
        limit: Número máximo de registros a retornar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista de imágenes del usuario
    """
    images = (
        db.query(Image)
        .filter(Image.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return images


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene información de una imagen específica
    
    Args:
        image_id: ID de la imagen
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
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


@router.delete("/{image_id}", status_code=status.HTTP_200_OK)
async def delete_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina una imagen WSI del usuario autenticado.

    Borra el registro en BD (con sus análisis, mapas de densidad y anotaciones
    asociados), descarta el slide de la caché, elimina el archivo WSI del disco
    y limpia el directorio de resultados de análisis cacheados.

    Args:
        image_id: ID de la imagen a eliminar
        db: Sesión de base de datos
        current_user: Usuario autenticado (debe ser el propietario)

    Returns:
        Mensaje de confirmación
    """
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imagen con ID {image_id} no encontrada"
        )

    if image.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar esta imagen"
        )

    file_path = image.file_path

    # Las anotaciones no están cubiertas por el cascade del ORM: se borran a mano
    # (sus análisis/mapas por annotation_id se eliminan vía cascade de la imagen).
    db.query(Annotation).filter(Annotation.image_id == image_id).delete(
        synchronize_session=False
    )
    # Cascade delete-orphan elimina analysis_results y density_maps de la imagen.
    db.delete(image)
    db.commit()

    # Liberar el archivo de la caché antes de borrarlo del disco (Windows lo
    # bloquea mientras OpenSlide lo mantenga abierto).
    try:
        slide_cache.evict(file_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"No se pudo descartar el slide de la caché: {e}")

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.error(f"Error eliminando archivo {file_path}: {e}")

    # Limpiar directorio de resultados de análisis cacheados de la imagen.
    analysis_dir = os.path.join(settings.UPLOAD_DIR, "analysis", str(image_id))
    if os.path.isdir(analysis_dir):
        try:
            shutil.rmtree(analysis_dir, ignore_errors=True)
        except OSError as e:
            logger.warning(f"Error limpiando análisis de la imagen: {e}")

    logger.info(f"Imagen eliminada: id={image_id}")
    return {"message": "Imagen eliminada correctamente", "id": image_id}


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
        existing_image = find_user_image(db, user_id, file.filename)
        if existing_image:
            return ImageUploadResult(
                filename=file.filename,
                success=False,
                message="Archivo ya existe",
                error=f"Archivo {file.filename} ya existe en el sistema"
            )
        
        # Guardar archivo con streaming, en la carpeta del usuario
        file_path = user_upload_path(user_id, file.filename)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sube múltiples imágenes WSI al servidor (soporte para drag & drop)

    Args:
        files: Lista de archivos a subir
        db: Sesión de base de datos
        current_user: Usuario autenticado (propietario de las imágenes)

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
        result = process_single_file(file, current_user.id, db)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el archivo DZI (Deep Zoom Image) con metadatos para OpenSeadragon.

    El XML lo genera DeepZoomGenerator para garantizar que la estructura de
    niveles, el tamaño de tile y el solapamiento coinciden exactamente con
    los tiles que sirve el endpoint de tiles.

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

    try:
        _, dzg = slide_cache.get_dzgenerator(image.file_path)
        dzi_xml = dzg.get_dzi("jpeg")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error generando DZI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando metadatos DZI: {str(e)}"
        )

    return Response(
        content=dzi_xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{image_id}/dzi_files/{level}/{col}_{row}.jpeg")
async def get_tile(
    image_id: int,
    level: int,
    col: int,
    row: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene un tile específico de la imagen WSI para OpenSeadragon.

    Usa DeepZoomGenerator (vía caché) que elige automáticamente el nivel
    de OpenSlide óptimo para cada nivel DZI y escala cuando es necesario,
    eliminando los tiles en blanco al cambiar de zoom. Los tiles ya
    renderizados se sirven desde una caché LRU en memoria.

    Args:
        image_id: ID de la imagen
        level: Nivel DZI (0 = más alejado, mayor número = más detalle)
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

    cache_headers = {"Cache-Control": "public, max-age=86400"}

    # 1. Servir desde caché de tiles si está disponible
    cached = slide_cache.get_tile_bytes(image.file_path, level, col, row)
    if cached is not None:
        return Response(
            content=cached,
            media_type="image/jpeg",
            headers={**cache_headers, "X-Tile-Cache": "HIT"},
        )

    try:
        _, dzg = slide_cache.get_dzgenerator(image.file_path)

        # Validar que el nivel solicitado existe en la pirámide DZI
        if level < 0 or level >= dzg.level_count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nivel DZI {level} fuera de rango (0-{dzg.level_count - 1})"
            )

        try:
            tile = dzg.get_tile(level, (col, row))
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tile fuera de los límites de la imagen"
            )

        # Convertir RGBA a RGB sobre fondo blanco
        if tile.mode == "RGBA":
            background = PILImage.new("RGB", tile.size, (255, 255, 255))
            background.paste(tile, mask=tile.split()[3])
            tile = background
        elif tile.mode != "RGB":
            tile = tile.convert("RGB")

        img_byte_arr = io.BytesIO()
        tile.save(img_byte_arr, format="JPEG", quality=85)
        tile_bytes = img_byte_arr.getvalue()

        # Guardar en caché para futuras peticiones
        slide_cache.store_tile_bytes(image.file_path, level, col, row, tile_bytes)

        return Response(
            content=tile_bytes,
            media_type="image/jpeg",
            headers={**cache_headers, "X-Tile-Cache": "MISS"},
        )

    except HTTPException:
        raise
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
