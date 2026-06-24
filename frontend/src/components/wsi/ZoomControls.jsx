import { useState, useEffect } from 'react';
import { Lightbulb } from 'lucide-react';
import './ZoomControls.css';

/**
 * Componente de controles de zoom personalizados para WSIViewer
 */
const ZoomControls = ({ viewerRef }) => {
  const [zoomLevel, setZoomLevel] = useState(100);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const updateZoomLevel = () => {
      const zoom = viewer.viewport.getZoom();
      const imageZoom = viewer.viewport.viewportToImageZoom(zoom);
      const percentage = Math.round(imageZoom * 100);
      setZoomLevel(percentage);
    };

    // Actualizar nivel de zoom inicialmente
    viewer.addHandler('open', updateZoomLevel);
    viewer.addHandler('zoom', updateZoomLevel);
    viewer.addHandler('animation-finish', updateZoomLevel);

    return () => {
      viewer.removeHandler('open', updateZoomLevel);
      viewer.removeHandler('zoom', updateZoomLevel);
      viewer.removeHandler('animation-finish', updateZoomLevel);
    };
  }, [viewerRef]);

  const handleZoomTo = percentage => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Convertir porcentaje a zoom de OpenSeadragon
    const imageZoom = percentage / 100;
    const viewportZoom = viewer.viewport.imageToViewportZoom(imageZoom);

    // Zoom al centro de la vista actual
    const currentCenter = viewer.viewport.getCenter();
    viewer.viewport.zoomTo(viewportZoom, currentCenter, true);
  };

  const handleZoomIn = () => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.viewport.zoomBy(1.5);
    viewer.viewport.applyConstraints();
  };

  const handleZoomOut = () => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.viewport.zoomBy(0.667);
    viewer.viewport.applyConstraints();
  };

  const handleResetZoom = () => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.viewport.goHome(true);
  };

  return (
    <div className="zoom-controls">
      <div className="zoom-level-display">
        <span className="zoom-percentage">{zoomLevel}%</span>
      </div>

      <div className="zoom-buttons-group">
        <button
          className="zoom-btn zoom-btn-preset"
          onClick={() => handleZoomTo(1)}
          title="Zoom 1%"
        >
          1%
        </button>
        <button
          className="zoom-btn zoom-btn-preset"
          onClick={() => handleZoomTo(10)}
          title="Zoom 10%"
        >
          10%
        </button>
        <button
          className="zoom-btn zoom-btn-preset"
          onClick={() => handleZoomTo(50)}
          title="Zoom 50%"
        >
          50%
        </button>
        <button
          className="zoom-btn zoom-btn-preset"
          onClick={() => handleZoomTo(100)}
          title="Zoom 100%"
        >
          100%
        </button>
        <button
          className="zoom-btn zoom-btn-preset"
          onClick={() => handleZoomTo(400)}
          title="Zoom 400%"
        >
          400%
        </button>
      </div>

      <div className="zoom-buttons-group">
        <button className="zoom-btn zoom-btn-control" onClick={handleZoomOut} title="Zoom Out">
          −
        </button>
        <button className="zoom-btn zoom-btn-control" onClick={handleResetZoom} title="Reset Zoom">
          ⌂
        </button>
        <button className="zoom-btn zoom-btn-control" onClick={handleZoomIn} title="Zoom In">
          +
        </button>
      </div>

      <div className="zoom-info">
        <small>
          <Lightbulb size={14} /> Usa scroll del ratón para zoom
          <br />
          Arrastra para navegar (pan)
        </small>
      </div>
    </div>
  );
};

export default ZoomControls;
