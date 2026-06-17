import { useEffect, useRef, useState } from 'react';
import OpenSeadragon from 'openseadragon';
import ZoomControls from './ZoomControls';
import './WSIViewer.css';

/**
 * Componente WSIViewer - Visualizador de imágenes WSI usando OpenSeadragon
 */
const WSIViewer = ({ imageId, apiBaseUrl, className = '', onError }) => {
  const viewerRef = useRef(null);
  const viewerInstanceRef = useRef(null);
  const [viewerState, setViewerState] = useState({
    isLoading: true,
    error: null,
  });
  const [viewerReady, setViewerReady] = useState(false);

  const hasRequiredProps = imageId && apiBaseUrl;

  useEffect(() => {
    if (!hasRequiredProps) {
      if (onError) onError(new Error('imageId y apiBaseUrl son requeridos'));
      return;
    }

    let mounted = true;

    const initViewer = () => {
      try {
        const dziUrl = `${apiBaseUrl}/images/${imageId}/dzi.dzi`;

        viewerInstanceRef.current = OpenSeadragon({
          element: viewerRef.current,
          prefixUrl: 'https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/',
          tileSources: dziUrl,
          showNavigator: true,
          showNavigationControl: false,
          navigatorPosition: 'BOTTOM_RIGHT',
          animationTime: 0.5,
          blendTime: 0.1,
          constrainDuringPan: true,
          maxZoomPixelRatio: 2,
          minZoomLevel: 0.8,
          visibilityRatio: 1,
          zoomPerScroll: 2,
          timeout: 120000,
          crossOriginPolicy: 'Anonymous',
        });

        viewerInstanceRef.current.addHandler('open', () => {
          console.log('WSI Image opened successfully');
          if (mounted) {
            setViewerState({ isLoading: false, error: null });
            setViewerReady(true);
          }
        });

        viewerInstanceRef.current.addHandler('open-failed', event => {
          const errorMsg = `Failed to open image: ${event.message || 'Unknown error'}`;
          console.error(errorMsg);
          if (mounted) {
            setViewerState({ isLoading: false, error: errorMsg });
          }
          if (onError) onError(new Error(errorMsg));
        });

        viewerInstanceRef.current.addHandler('tile-load-failed', event => {
          console.error('Tile load failed:', event);
        });
      } catch (err) {
        const errorMsg = `Error initializing viewer: ${err.message}`;
        console.error(errorMsg, err);
        if (mounted) {
          setViewerState({ isLoading: false, error: errorMsg });
        }
        if (onError) onError(err);
      }
    };

    initViewer();

    return () => {
      mounted = false;
      if (viewerInstanceRef.current) {
        viewerInstanceRef.current.destroy();
        viewerInstanceRef.current = null;
      }
    };
  }, [imageId, apiBaseUrl, onError, hasRequiredProps]);

  return (
    <div className={`wsi-viewer-container ${className}`}>
      {!hasRequiredProps && (
        <div className="wsi-viewer-error">
          <p>❌ Error: imageId y apiBaseUrl son requeridos</p>
        </div>
      )}
      {hasRequiredProps && viewerState.isLoading && (
        <div className="wsi-viewer-loading">
          <div className="spinner"></div>
          <p>Cargando imagen WSI...</p>
        </div>
      )}
      {hasRequiredProps && viewerState.error && (
        <div className="wsi-viewer-error">
          <p>❌ Error: {viewerState.error}</p>
        </div>
      )}
      <div ref={viewerRef} className="wsi-viewer" style={{ width: '100%', height: '100%' }}></div>
      {viewerReady && <ZoomControls viewerRef={viewerInstanceRef} />}
    </div>
  );
};

export default WSIViewer;
