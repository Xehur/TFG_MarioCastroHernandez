import { useEffect, useRef, useState } from 'react';
import OpenSeadragon from 'openseadragon';
import { imageService } from '../../services/imageService';
import { authService } from '../../services/authService';
import { createPerfMonitor } from '../../utils/perfMonitor';
import ZoomControls from './ZoomControls';
import ViewerInfoBar from './ViewerInfoBar';
import './WSIViewer.css';

/**
 * Componente WSIViewer - Visualizador de imágenes WSI usando OpenSeadragon
 */
const WSIViewer = ({ imageId, apiBaseUrl, className = '', onError }) => {
  const viewerRef = useRef(null);
  const viewerInstanceRef = useRef(null);
  const perfMonitorRef = useRef(null);
  const [viewerState, setViewerState] = useState({
    isLoading: true,
    error: null,
  });
  const [viewerReady, setViewerReady] = useState(false);
  const [tilesLoading, setTilesLoading] = useState(false);
  const [imageMetadata, setImageMetadata] = useState(null);

  const hasRequiredProps = imageId && apiBaseUrl;

  useEffect(() => {
    if (!hasRequiredProps) {
      if (onError) onError(new Error('imageId y apiBaseUrl son requeridos'));
      return;
    }

    let mounted = true;

    const initViewer = () => {
      try {
        const dziUrl = imageService.getDziUrl(imageId);

        // Las peticiones de tiles/DZI deben llevar el token JWT. OpenSeadragon
        // carga los tiles como peticiones AJAX para poder añadir la cabecera.
        const token = authService.getToken();
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

        viewerInstanceRef.current = OpenSeadragon({
          element: viewerRef.current,
          prefixUrl: 'https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/',
          tileSources: dziUrl,
          loadTilesWithAjax: true,
          ajaxHeaders: authHeaders,
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
          // --- Optimización de carga (ISSUE 17) ---
          // Caché de tiles: mantiene más tiles en memoria para re-zoom rápido
          maxImageCacheCount: 500,
          // Descargas de tiles en paralelo (lazy loading eficiente)
          imageLoaderLimit: 6,
          // Precarga tiles adyacentes para transiciones más suaves
          preload: true,
          // Mantiene visibles los tiles de menor resolución hasta que cargan
          // los de mayor resolución (evita que partes "desaparezcan" al hacer zoom)
          immediateRender: false,
          placeholderFillStyle: '#1a1a1a',
          // Suaviza los bordes entre tiles
          smoothTileEdgesMinZoom: 1.1,
        });

        const perf = createPerfMonitor(viewerInstanceRef.current);
        perfMonitorRef.current = perf;

        viewerInstanceRef.current.addHandler('open', () => {
          console.log('WSI Image opened successfully');
          if (mounted) {
            setViewerState({ isLoading: false, error: null });
            setViewerReady(true);

            // Obtener metadatos de la imagen
            const tiledImage = viewerInstanceRef.current.world.getItemAt(0);
            if (tiledImage) {
              const imageSize = tiledImage.getContentSize();
              setImageMetadata({
                width: Math.round(imageSize.x),
                height: Math.round(imageSize.y),
                level_count: tiledImage.source.maxLevel + 1 || 'N/A',
              });

              // Indicador de carga de tiles: se activa mientras faltan tiles
              // por renderizar y se apaga cuando la vista está completa
              tiledImage.addHandler('fully-loaded-change', event => {
                if (mounted) setTilesLoading(!event.fullyLoaded);
              });
            }
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
      if (perfMonitorRef.current) {
        perfMonitorRef.current.destroy();
        perfMonitorRef.current = null;
      }
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
      {viewerReady && tilesLoading && (
        <div className="wsi-tiles-loading" role="status" aria-live="polite">
          <div className="spinner spinner-small"></div>
          <span>Cargando tiles…</span>
        </div>
      )}
      {viewerReady && <ZoomControls viewerRef={viewerInstanceRef} />}
      {viewerReady && <ViewerInfoBar viewerRef={viewerInstanceRef} imageMetadata={imageMetadata} />}
    </div>
  );
};

export default WSIViewer;
