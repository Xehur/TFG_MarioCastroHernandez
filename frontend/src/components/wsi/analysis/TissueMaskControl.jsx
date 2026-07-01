import { useState, useEffect, useRef, useCallback } from 'react';
import { ScanSearch, Eye, EyeOff, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { tissueService } from '../../../services/tissueService';
import './TissueMaskControl.css';

/**
 * Control del visor de máscara de tejido (issue 38).
 *
 * Añade un overlay de la máscara de tejido sobre la imagen base de
 * OpenSeadragon, con toggle de visibilidad, ajuste de opacidad y estadísticas
 * (% de tejido).
 *
 * Props:
 * - viewer: instancia de OpenSeadragon (o null si aún no está lista)
 * - imageId: id de la imagen
 */
const TissueMaskControl = ({ viewer, imageId }) => {
  const [enabled, setEnabled] = useState(false);
  const [opacity, setOpacity] = useState(0.5);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  const maskItemRef = useRef(null);
  const objectUrlRef = useRef(null);

  const removeOverlay = useCallback(() => {
    if (viewer && maskItemRef.current) {
      try {
        viewer.world.removeItem(maskItemRef.current);
      } catch {
        // El item puede haberse eliminado ya al destruir el visor.
      }
    }
    maskItemRef.current = null;
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, [viewer]);

  // Limpieza al desmontar
  useEffect(() => removeOverlay, [removeOverlay]);

  const showMask = useCallback(
    (url) => {
      if (!viewer) return;
      viewer.addSimpleImage({
        url,
        opacity,
        success: event => {
          maskItemRef.current = event.item;
          event.item.setOpacity(opacity);
        },
      });
    },
    [viewer, opacity]
  );

  const addOverlay = useCallback(async () => {
    if (!viewer) return;
    setLoading(true);
    setError(null);
    try {
      const [statData, url] = await Promise.all([
        tissueService.getStats(imageId),
        tissueService.getMaskObjectUrl(imageId),
      ]);
      setStats(statData.result_data || null);
      objectUrlRef.current = url;
      showMask(url);
    } catch (err) {
      setError(
        err.response?.data?.detail || err.message || 'Error al cargar la máscara'
      );
      setEnabled(false);
    } finally {
      setLoading(false);
    }
  }, [viewer, imageId, showMask]);

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    if (next) {
      addOverlay();
    } else {
      removeOverlay();
    }
  };

  const handleOpacityChange = value => {
    setOpacity(value);
    if (maskItemRef.current) {
      maskItemRef.current.setOpacity(value);
    }
  };

  const handleReanalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      removeOverlay();
      await tissueService.analyze(imageId);
      const [statData, url] = await Promise.all([
        tissueService.getStats(imageId),
        tissueService.getMaskObjectUrl(imageId),
      ]);
      setStats(statData.result_data || null);
      objectUrlRef.current = url;
      showMask(url);
      setEnabled(true);
    } catch (err) {
      setError(
        err.response?.data?.detail || err.message || 'Error al re-analizar'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tissue-control">
      <div className="tissue-control-header">
        <ScanSearch size={16} />
        <span>Máscara de tejido</span>
      </div>

      <button
        type="button"
        className={`tissue-toggle ${enabled ? 'active' : ''}`}
        onClick={handleToggle}
        disabled={loading || !viewer}
      >
        {loading ? (
          <Loader2 size={15} className="tissue-spin" />
        ) : enabled ? (
          <Eye size={15} />
        ) : (
          <EyeOff size={15} />
        )}
        <span>{enabled ? 'Ocultar' : 'Mostrar'}</span>
      </button>

      {enabled && (
        <div className="tissue-opacity">
          <label htmlFor="tissue-opacity">Opacidad</label>
          <input
            id="tissue-opacity"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={e => handleOpacityChange(Number(e.target.value))}
          />
          <span className="tissue-opacity-value">
            {Math.round(opacity * 100)}%
          </span>
        </div>
      )}

      {stats && (
        <div className="tissue-stats">
          <div className="tissue-stat">
            <span className="tissue-stat-label">Tejido</span>
            <span className="tissue-stat-value">
              {stats.tissue_percent?.toFixed(1)}%
            </span>
          </div>
          <button
            type="button"
            className="tissue-reanalyze"
            onClick={handleReanalyze}
            disabled={loading}
            title="Re-analizar"
          >
            <RefreshCw size={13} /> Re-analizar
          </button>
        </div>
      )}

      {error && (
        <p className="tissue-error">
          <AlertCircle size={14} /> {error}
        </p>
      )}
    </div>
  );
};

export default TissueMaskControl;
