import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { WSIViewer } from '../../components/wsi';
import { imageService } from '../../services/imageService';
import config from '../../config/config';
import './ImageViewer.css';

const ImageViewer = () => {
  const { imageId } = useParams();
  const navigate = useNavigate();
  const [imageInfo, setImageInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchImageInfo = async () => {
      try {
        setLoading(true);
        const data = await imageService.getImageById(imageId);
        setImageInfo(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching image info:', err);
        setError('No se pudo cargar la información de la imagen');
      } finally {
        setLoading(false);
      }
    };

    if (imageId) {
      fetchImageInfo();
    }
  }, [imageId]);

  const handleViewerError = error => {
    console.error('WSI Viewer error:', error);
    setError(`Error al cargar la imagen: ${error.message}`);
  };

  if (loading) {
    return (
      <div className="image-viewer-page loading">
        <div className="spinner"></div>
        <p>Cargando información de la imagen...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="image-viewer-page error">
        <h2>❌ Error</h2>
        <p>{error}</p>
        <button onClick={() => navigate('/')}>Volver al inicio</button>
      </div>
    );
  }

  return (
    <div className="image-viewer-page">
      <header className="image-viewer-header">
        <button className="back-button" onClick={() => navigate('/')}>
          ← Volver
        </button>
        <div className="image-info">
          <h1>{imageInfo?.filename}</h1>
          <div className="image-metadata">
            <span>
              📐 {imageInfo?.width} x {imageInfo?.height} px
            </span>
            <span>📊 {imageInfo?.level_count} niveles</span>
            <span>💾 {imageInfo?.file_size_mb} MB</span>
          </div>
        </div>
      </header>

      <div className="image-viewer-content">
        <WSIViewer
          imageId={parseInt(imageId)}
          apiBaseUrl={config.apiBaseUrl}
          onError={handleViewerError}
        />
      </div>
    </div>
  );
};

export default ImageViewer;
