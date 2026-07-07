import {
  useState,
  useRef,
  useCallback,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from 'react';
import { Brain, Eye, EyeOff, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { aiClassificationService } from '../../../services/aiClassificationService';
import './AIClassificationControl.css';

/**
 * Control de clasificación de tejido por IA (Sprint 7).
 *
 * Superpone el mapa de clases generado por el modelo de IA sobre la imagen base
 * de OpenSeadragon, con toggle de visibilidad, opacidad, leyenda de clases y
 * distribución por grupo (tumoral, estroma, no tumoral, necrosis).
 *
 * Props:
 * - viewer: instancia de OpenSeadragon (o null si aún no está lista)
 * - imageId: id de la imagen
 *
 * Ref imperativa (para la paleta de comandos):
 * - toggle(): alterna la visibilidad del mapa.
 * - show(): fuerza que el mapa se muestre.
 */
const AIClassificationControl = forwardRef(({ viewer, imageId }, ref) => {
  const [enabled, setEnabled] = useState(false);
  const [opacity, setOpacity] = useState(0.55);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  const mapItemRef = useRef(null);
  const objectUrlRef = useRef(null);

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

  useEffect(() => removeOverlay, [removeOverlay]);

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
          aiClassificationService.getStats(imageId, { force }),
          aiClassificationService.getMapObjectUrl(imageId, { force }),
        ]);
        setStats(statData.result_data || null);
        objectUrlRef.current = url;
        showMap(url);
      } catch (err) {
        setError(
          err.response?.data?.detail || err.message || 'Error al clasificar'
        );
        setEnabled(false);
      } finally {
        setLoading(false);
      }
    },
    [viewer, imageId, removeOverlay, showMap]
  );

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    if (next) {
      load();
    } else {
      removeOverlay();
    }
  };

  const toggleRef = useRef(handleToggle);
  toggleRef.current = handleToggle;

  const ensureShown = useCallback(() => {
    setEnabled(true);
    load();
  }, [load]);
  const showRef = useRef(ensureShown);
  showRef.current = ensureShown;

  useImperativeHandle(
    ref,
    () => ({
      toggle: () => toggleRef.current(),
      show: () => showRef.current(),
    }),
    []
  );

  const handleOpacityChange = value => {
    setOpacity(value);
    if (mapItemRef.current) {
      mapItemRef.current.setOpacity(value);
    }
  };

  const groups = (stats?.groups || []).filter(g => g.percent > 0);
  const dominant = stats?.classes?.find(c => c.code === stats.dominant_class);

  return (
    <div className="ai-control">
      <div className="ai-control-header">
        <Brain size={16} />
        <span>Clasificación IA</span>
      </div>

      <button
        type="button"
        className={`ai-toggle ${enabled ? 'active' : ''}`}
        onClick={handleToggle}
        disabled={loading || !viewer}
      >
        {loading ? (
          <Loader2 size={15} className="ai-spin" />
        ) : enabled ? (
          <Eye size={15} />
        ) : (
          <EyeOff size={15} />
        )}
        <span>{enabled ? 'Ocultar' : 'Mostrar'}</span>
      </button>

      {enabled && (
        <div className="ai-opacity">
          <label htmlFor="ai-opacity">Opacidad</label>
          <input
            id="ai-opacity"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={e => handleOpacityChange(Number(e.target.value))}
          />
          <span className="ai-opacity-value">{Math.round(opacity * 100)}%</span>
        </div>
      )}

      {stats && dominant && (
        <div className="ai-dominant">
          <span className="ai-dominant-label">Predominante</span>
          <span className="ai-dominant-value">
            <span
              className="ai-chip"
              style={{
                background: `rgb(${(dominant.group_color || dominant.color).join(
                  ','
                )})`,
              }}
            />
            {dominant.name} · {dominant.percent.toFixed(0)}%
          </span>
        </div>
      )}

      {stats && groups.length > 0 && (
        <div className="ai-groups">
          {groups.map(g => (
            <div key={g.group} className="ai-group">
              <div className="ai-group-head">
                <span
                  className="ai-chip"
                  style={{ background: `rgb(${g.color.join(',')})` }}
                />
                <span className="ai-group-name">{g.group}</span>
                <span className="ai-group-pct">{g.percent.toFixed(1)}%</span>
              </div>
              <div className="ai-bar">
                <div
                  className="ai-bar-fill"
                  style={{
                    width: `${Math.min(100, g.percent)}%`,
                    background: `rgb(${g.color.join(',')})`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {stats && (
        <div className="ai-footer">
          <span className="ai-model" title={stats.model?.id}>
            {stats.model?.dataset || 'IA'}
          </span>
          <button
            type="button"
            className="ai-reanalyze"
            onClick={() => load({ force: true })}
            disabled={loading}
            title="Re-clasificar"
          >
            <RefreshCw size={13} /> Re-clasificar
          </button>
        </div>
      )}

      {error && (
        <p className="ai-error">
          <AlertCircle size={14} /> {error}
        </p>
      )}
    </div>
  );
});

AIClassificationControl.displayName = 'AIClassificationControl';

export default AIClassificationControl;
