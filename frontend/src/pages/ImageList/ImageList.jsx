import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  LayoutGrid,
  Plus,
  FolderOpen,
  Ruler,
  Layers,
  HardDrive,
  Calendar,
  Eye,
  Trash2,
} from 'lucide-react';
import { imageService } from '../../services/imageService';
import { formatFileSize, formatDate } from '../../utils/helpers';
import UserMenu from '../../components/auth/UserMenu';
import './ImageList.css';

/**
 * Página de lista de imágenes WSI
 */
const ImageList = () => {
  const navigate = useNavigate();
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    const loadImages = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await imageService.getImages();
        setImages(data);
      } catch (err) {
        setError(err.message || 'Error al cargar las imágenes');
        console.error('Error loading images:', err);
      } finally {
        setLoading(false);
      }
    };

    loadImages();
  }, []);

  const loadImagesManually = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await imageService.getImages();
      setImages(data);
    } catch (err) {
      setError(err.message || 'Error al cargar las imágenes');
      console.error('Error loading images:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleViewImage = imageId => {
    navigate(`/viewer/${imageId}`);
  };

  const handleUploadNew = () => {
    navigate('/upload');
  };

  const handleAskDelete = (e, imageId) => {
    e.stopPropagation();
    setConfirmDeleteId(imageId);
  };

  const handleCancelDelete = e => {
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  const handleConfirmDelete = async (e, imageId) => {
    e.stopPropagation();
    try {
      setDeletingId(imageId);
      await imageService.deleteImage(imageId);
      setImages(prev => prev.filter(img => img.id !== imageId));
      setConfirmDeleteId(null);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setError(typeof detail === 'string' ? detail : 'No se pudo eliminar la imagen');
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="image-list-page loading">
        <div className="spinner"></div>
        <p>Cargando imágenes...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="image-list-page error">
        <h2>
          <AlertCircle size={22} /> Error
        </h2>
        <p>{error}</p>
        <button onClick={loadImagesManually}>Reintentar</button>
      </div>
    );
  }

  return (
    <div className="image-list-page">
      <div className="image-list-header">
        <div className="header-title">
          <h1>
            <LayoutGrid size={24} /> Imágenes WSI
          </h1>
          <p>{images.length} imagen(es) disponible(s)</p>
        </div>
        <div className="header-actions">
          <button className="upload-btn" onClick={handleUploadNew}>
            <Plus size={16} /> Subir nueva imagen
          </button>
          <UserMenu />
        </div>
      </div>

      {images.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <FolderOpen size={48} />
          </div>
          <h2>No hay imágenes</h2>
          <p>Sube tu primera imagen WSI para comenzar</p>
          <button className="upload-btn-large" onClick={handleUploadNew}>
            <Plus size={18} /> Subir imagen
          </button>
        </div>
      ) : (
        <div className="images-grid">
          {images.map(image => (
            <div key={image.id} className="image-card" onClick={() => handleViewImage(image.id)}>
              <div className="image-card-header">
                <h3>{image.filename}</h3>
                <span className="image-format">{image.format || 'WSI'}</span>
              </div>

              <div className="image-card-info">
                <div className="info-row">
                  <span className="info-label">
                    <Ruler size={15} /> Dimensiones:
                  </span>
                  <span className="info-value">
                    {image.width} × {image.height}
                  </span>
                </div>

                <div className="info-row">
                  <span className="info-label">
                    <Layers size={15} /> Niveles:
                  </span>
                  <span className="info-value">{image.level_count || 'N/A'}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">
                    <HardDrive size={15} /> Tamaño:
                  </span>
                  <span className="info-value">{formatFileSize(image.file_size_mb)}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">
                    <Calendar size={15} /> Subido:
                  </span>
                  <span className="info-value">{formatDate(image.created_at)}</span>
                </div>
              </div>

              <div className="image-card-footer">
                {confirmDeleteId === image.id ? (
                  <div className="delete-confirm" onClick={e => e.stopPropagation()}>
                    <span className="delete-confirm-text">¿Eliminar imagen?</span>
                    <div className="delete-confirm-actions">
                      <button
                        className="delete-cancel-btn"
                        onClick={handleCancelDelete}
                        disabled={deletingId === image.id}
                      >
                        Cancelar
                      </button>
                      <button
                        className="delete-confirm-btn"
                        onClick={e => handleConfirmDelete(e, image.id)}
                        disabled={deletingId === image.id}
                      >
                        {deletingId === image.id ? 'Eliminando…' : 'Eliminar'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="card-actions">
                    <button className="view-btn">
                      <Eye size={16} /> Ver imagen
                    </button>
                    <button
                      className="delete-btn"
                      onClick={e => handleAskDelete(e, image.id)}
                      title="Eliminar imagen"
                      aria-label="Eliminar imagen"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ImageList;
