import { useState, useEffect, useRef, useCallback } from 'react';
import { Grid3x3, Eye, EyeOff, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import OpenSeadragon from 'openseadragon';
import { densityService } from '../../../services/densityService';
import './DensityMapViewer.css';

const GRID_OPTIONS = [
  { value: 128, label: '128 px (fino)' },
  { value: 256, label: '256 px' },
  { value: 512, label: '512 px' },
  { value: 1024, label: '1024 px (grueso)' },
];

const COLORMAP_OPTIONS = ['viridis', 'hot', 'magma', 'plasma', 'inferno', 'jet'];

/**
 * Visor del mapa de densidades (issue 39).
 *
 * Superpone un heatmap de densidad de tejido sobre la imagen base de
 * OpenSeadragon, con toggle de visibilidad, ajuste de opacidad, selección de
 * tamaño de grid y colormap, colorbar con escala y tooltip de densidad al
 * pasar el ratón.
 *
 * Props:
 * - viewer: instancia de OpenSeadragon (o null si aún no está lista)
 * - imageId: id de la imagen
 */
const DensityMapViewer = ({ viewer, imageId }) => {
  const [enabled, setEnabled] = useState(false);
  const [opacity, setOpacity] = useState(0.6);
  const [gridSize, setGridSize] = useState(256);
  const [colormap, setColormap] = useState('viridis');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [tooltip, setTooltip] = useState(null);

  const mapItemRef = useRef(null);
  const objectUrlRef = useRef(null);
  const trackerRef = useRef(null);
  const statsRef = useRef(null);

  const removeOverlay = useCallback(() => {
    if (viewer && mapItemRef.current) {
      try {
        viewer.world.removeItem(mapItemRef.current);
      } catch {
        // El item puede haberse eliminado ya al destruir el visor.
      }
    }
    mapItemRef.current = null;
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, [viewer]);

  const destroyTracker = useCallback(() => {
    if (trackerRef.current) {
      trackerRef.current.destroy();
      trackerRef.current = null;
    }
    setTooltip(null);
  }, []);

  // Limpieza al desmontar
  useEffect(() => {
    return () => {
      removeOverlay();
      destroyTracker();
    };
  }, [removeOverlay, destroyTracker]);

  const densityAt = useCallback((imageX, imageY) => {
    const data = statsRef.current;
    if (!data || !Array.isArray(data.matrix)) return null;
    const gs = data.grid_size || gridSize;
    const col = Math.floor(imageX / gs);
    const row = Math.floor(imageY / gs);
    if (row < 0 || col < 0 || row >= data.rows || col >= data.cols) return null;
    const value = data.matrix[row]?.[col];
    return typeof value === 'number' ? value : null;
  }, [gridSize]);

  const setupTracker = useCallback(() => {
    if (!viewer || trackerRef.current) return;
    trackerRef.current = new OpenSeadragon.MouseTracker({
      element: viewer.canvas,
      moveHandler: event => {
        if (!viewer.viewport) return;
        const viewportPoint = viewer.viewport.pointFromPixel(event.position);
        const imagePoint = viewer.viewport.viewportToImageCoordinates(viewportPoint);
        const value = densityAt(imagePoint.x, imagePoint.y);
        if (value == null) {
          setTooltip(null);
          return;
        }
        const oe = event.originalEvent;
        setTooltip({
          x: oe.clientX,
          y: oe.clientY,
          value,
        });
      },
      leaveHandler: () => setTooltip(null),
    });
  }, [viewer, densityAt]);

  const showMap = useCallback(
    url => {
      if (!viewer) return;
      viewer.addSimpleImage({
        url,
        opacity,
        success: event => {
          mapItemRef.current = event.item;
          event.item.setOpacity(opacity);
        },
      });
    },
    [viewer, opacity]
  );

  const load = useCallback(
    async ({ force = false } = {}) => {
      if (!viewer) return;
      setLoading(true);
      setError(null);
      removeOverlay();
      try {
        const [statData, url] = await Promise.all([
          densityService.getStats(imageId, { gridSize, colormap, force }),
          densityService.getMapObjectUrl(imageId, { gridSize, colormap, force }),
        ]);
        const data = statData.density_data || null;
        setStats(data);
        statsRef.current = data;
        objectUrlRef.current = url;
        showMap(url);
        setupTracker();
      } catch (err) {
        setError(
          err.response?.data?.detail || err.message || 'Error al cargar el mapa'
        );
        setEnabled(false);
      } finally {
        setLoading(false);
      }
    },
    [viewer, imageId, gridSize, colormap, removeOverlay, showMap, setupTracker]
  );

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    if (next) {
      load();
    } else {
      removeOverlay();
      destroyTracker();
    }
  };

  const handleOpacityChange = value => {
    setOpacity(value);
    if (mapItemRef.current) {
      mapItemRef.current.setOpacity(value);
    }
  };

  const handleParamChange = (setter, value) => {
    setter(value);
  };

  // Al cambiar grid o colormap con el mapa activo, recargar con los valores
  // ya actualizados (evita el closure obsoleto de un setTimeout).
  useEffect(() => {
    if (!enabled) return;
    load({ force: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gridSize, colormap]);

  const gradientCss = stats?.colorbar
    ? `linear-gradient(to top, ${stats.colorbar
        .map(c => `rgb(${c[0]}, ${c[1]}, ${c[2]})`)
        .join(', ')})`
    : 'linear-gradient(to top, #440154, #21918c, #fde725)';

  return (
    <div className="density-control">
      <div className="density-control-header">
        <Grid3x3 size={16} />
        <span>Mapa de densidad</span>
      </div>

      <div className="density-params">
        <label className="density-param">
          <span>Grid</span>
          <select
            value={gridSize}
            onChange={e => handleParamChange(setGridSize, Number(e.target.value))}
            disabled={loading}
          >
            {GRID_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="density-param">
          <span>Color</span>
          <select
            value={colormap}
            onChange={e => handleParamChange(setColormap, e.target.value)}
            disabled={loading}
          >
            {COLORMAP_OPTIONS.map(cm => (
              <option key={cm} value={cm}>
                {cm}
              </option>
            ))}
          </select>
        </label>
      </div>

      <button
        type="button"
        className={`density-toggle ${enabled ? 'active' : ''}`}
        onClick={handleToggle}
        disabled={loading || !viewer}
      >
        {loading ? (
          <Loader2 size={15} className="density-spin" />
        ) : enabled ? (
          <Eye size={15} />
        ) : (
          <EyeOff size={15} />
        )}
        <span>{enabled ? 'Ocultar' : 'Mostrar'}</span>
      </button>

      {enabled && (
        <div className="density-opacity">
          <label htmlFor="density-opacity">Opacidad</label>
          <input
            id="density-opacity"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={e => handleOpacityChange(Number(e.target.value))}
          />
          <span className="density-opacity-value">
            {Math.round(opacity * 100)}%
          </span>
        </div>
      )}

      {enabled && stats && (
        <div className="density-legend">
          <div className="density-colorbar" style={{ background: gradientCss }} />
          <div className="density-scale">
            <span>{(stats.density_max ?? 0).toFixed(2)}</span>
            <span className="density-scale-label">densidad</span>
            <span>{(stats.density_min ?? 0).toFixed(2)}</span>
          </div>
        </div>
      )}

      {stats && (
        <div className="density-stats">
          <div className="density-stat">
            <span className="density-stat-label">Media</span>
            <span className="density-stat-value">
              {((stats.density_mean ?? 0) * 100).toFixed(1)}%
            </span>
          </div>
          <button
            type="button"
            className="density-reanalyze"
            onClick={() => load({ force: true })}
            disabled={loading}
            title="Re-generar"
          >
            <RefreshCw size={13} /> Re-generar
          </button>
        </div>
      )}

      {error && (
        <p className="density-error">
          <AlertCircle size={14} /> {error}
        </p>
      )}

      {tooltip && (
        <div
          className="density-tooltip"
          style={{ left: tooltip.x + 14, top: tooltip.y + 14 }}
        >
          Densidad: {(tooltip.value * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
};

export default DensityMapViewer;
