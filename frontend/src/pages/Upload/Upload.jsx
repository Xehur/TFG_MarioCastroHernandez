import { useNavigate } from 'react-router-dom';
import { ImageDropZone } from '../../components/upload';
import './Upload.css';

/**
 * Página de carga de imágenes WSI
 */
const Upload = () => {
  const navigate = useNavigate();

  const handleUploadComplete = response => {
    console.log('Upload completed:', response);
    // Opcional: Mostrar notificación de éxito
  };

  const handleUploadError = error => {
    console.error('Upload error:', error);
    // Opcional: Mostrar notificación de error
  };

  const handleViewImages = () => {
    navigate('/');
  };

  return (
    <div className="upload-page">
      <div className="upload-header">
        <div className="upload-title">
          <h1>📤 Subir Imágenes WSI</h1>
          <p>Carga tus imágenes de Whole Slide Image para visualización y análisis</p>
        </div>
        <button className="view-images-btn" onClick={handleViewImages}>
          📋 Ver imágenes
        </button>
      </div>

      <div className="upload-content">
        <ImageDropZone onUploadComplete={handleUploadComplete} onUploadError={handleUploadError} />
      </div>

      <div className="upload-info">
        <div className="info-card">
          <h3>ℹ️ Formatos soportados</h3>
          <ul>
            <li>.svs (Aperio)</li>
            <li>.tif, .tiff (Generic TIFF)</li>
            <li>.ndpi (Hamamatsu)</li>
            <li>.vms, .vmu (Ventana)</li>
            <li>.scn (Leica)</li>
            <li>.mrxs (MIRAX)</li>
            <li>.bif (Ventana BigTIFF)</li>
          </ul>
        </div>

        <div className="info-card">
          <h3>📏 Límites</h3>
          <ul>
            <li>Tamaño máximo: 2GB por archivo</li>
            <li>Múltiples archivos permitidos</li>
            <li>Formatos validados automáticamente</li>
          </ul>
        </div>

        <div className="info-card">
          <h3>🚀 Cómo usarlo</h3>
          <ul>
            <li>Arrastra archivos a la zona de carga</li>
            <li>O haz clic para seleccionar archivos</li>
            <li>Revisa la lista antes de subir</li>
            <li>Haz clic en &quot;Subir todos&quot; para comenzar</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Upload;
