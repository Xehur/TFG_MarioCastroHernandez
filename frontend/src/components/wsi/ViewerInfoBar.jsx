import { useState, useEffect } from 'react';
import OpenSeadragon from 'openseadragon';
import './ViewerInfoBar.css';

/**
 * Barra de información del visor - muestra coordenadas, dimensiones y controles
 */
const ViewerInfoBar = ({ viewerRef, imageMetadata }) => {
  const [mouseCoords, setMouseCoords] = useState({ x: 0, y: 0 });
  const [currentZoomLevel, setCurrentZoomLevel] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Actualizar coordenadas del mouse
    const handleMouseMove = event => {
      if (!viewer.viewport) return;

      // Obtener posición del mouse relativa al canvas
      const webPoint = event.position;
      const viewportPoint = viewer.viewport.pointFromPixel(webPoint);
      const imagePoint = viewer.viewport.viewportToImageCoordinates(viewportPoint);

      setMouseCoords({
        x: Math.round(imagePoint.x),
        y: Math.round(imagePoint.y),
      });
    };

    // Crear un tracker personalizado para el mouse
    const mouseTracker = new OpenSeadragon.MouseTracker({
      element: viewer.canvas,
      moveHandler: handleMouseMove,
    });

    // Actualizar nivel de zoom
    const handleZoom = () => {
      const zoom = viewer.viewport.getZoom();
      const imageZoom = viewer.viewport.viewportToImageZoom(zoom);
      const percentage = Math.round(imageZoom * 100);
      setCurrentZoomLevel(percentage);
    };

    // Registrar event handlers
    viewer.addHandler('zoom', handleZoom);
    viewer.addHandler('open', handleZoom);

    // Cleanup
    return () => {
      mouseTracker.destroy();
      viewer.removeHandler('zoom', handleZoom);
      viewer.removeHandler('open', handleZoom);
    };
  }, [viewerRef]);

  // Detectar cambios en fullscreen
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const handleFullscreen = () => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const container = viewer.element;

    if (!document.fullscreenElement) {
      container.requestFullscreen().catch(err => {
        console.error('Error entering fullscreen:', err);
      });
    } else {
      document.exitFullscreen();
    }
  };

  const handleGoHome = () => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.viewport.goHome(true);
  };

  return (
    <div className="viewer-info-bar">
      {/* Sección izquierda - Información de la imagen */}
      <div className="info-section">
        {imageMetadata && (
          <>
            <div className="info-item">
              <span className="info-label">Dimensiones:</span>
              <span className="info-value">
                {imageMetadata.width} × {imageMetadata.height} px
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">Niveles:</span>
              <span className="info-value">{imageMetadata.level_count || 'N/A'}</span>
            </div>
          </>
        )}
      </div>

      {/* Sección central - Coordenadas del mouse */}
      <div className="info-section center">
        <div className="info-item">
          <span className="info-label">🖱️ Coordenadas:</span>
          <span className="info-value coords">
            X: {mouseCoords.x} | Y: {mouseCoords.y}
          </span>
        </div>
        <div className="info-item">
          <span className="info-label">🔍 Zoom:</span>
          <span className="info-value">{currentZoomLevel}%</span>
        </div>
      </div>

      {/* Sección derecha - Controles */}
      <div className="info-section controls">
        <button className="control-btn" onClick={handleGoHome} title="Volver a vista inicial">
          <span className="btn-icon">🏠</span>
          <span className="btn-label">Home</span>
        </button>
        <button
          className="control-btn"
          onClick={handleFullscreen}
          title={isFullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}
        >
          <span className="btn-icon">{isFullscreen ? '⛶' : '⛶'}</span>
          <span className="btn-label">{isFullscreen ? 'Exit' : 'Fullscreen'}</span>
        </button>
      </div>
    </div>
  );
};

export default ViewerInfoBar;
