import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
        <h2>❌ Error</h2>
        <p>{error}</p>
        <button onClick={loadImagesManually}>Reintentar</button>
      </div>
    );
  }

  return (
    <div className="image-list-page">
      <div className="image-list-header">
        <div className="header-title">
          <h1>📋 Imágenes WSI</h1>
          <p>{images.length} imagen(es) disponible(s)</p>
        </div>
        <div className="header-actions">
          <button className="upload-btn" onClick={handleUploadNew}>
            ➕ Subir nueva imagen
          </button>
          <UserMenu />
        </div>
      </div>

      {images.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📂</div>
          <h2>No hay imágenes</h2>
          <p>Sube tu primera imagen WSI para comenzar</p>
          <button className="upload-btn-large" onClick={handleUploadNew}>
            ➕ Subir imagen
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
                  <span className="info-label">📐 Dimensiones:</span>
                  <span className="info-value">
                    {image.width} × {image.height}
                  </span>
                </div>

                <div className="info-row">
                  <span className="info-label">📊 Niveles:</span>
                  <span className="info-value">{image.level_count || 'N/A'}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">💾 Tamaño:</span>
                  <span className="info-value">{formatFileSize(image.file_size_mb)}</span>
                </div>

                <div className="info-row">
                  <span className="info-label">📅 Subido:</span>
                  <span className="info-value">{formatDate(image.created_at)}</span>
                </div>
              </div>

              <div className="image-card-footer">
                <button className="view-btn">👁️ Ver imagen</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ImageList;
