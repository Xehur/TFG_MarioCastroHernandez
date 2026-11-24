import {
  useState,
  useEffect,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from 'react';
import {
  ScanSearch,
  Eye,
  EyeOff,
  Loader2,
  AlertCircle,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react';
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
 *
 * Umbral ajustable: un deslizador cambia el factor de umbral del detector
 * (1 = automático; menos = más tejido; más = menos tejido) y muestra al momento
 * una vista previa sin guardarla. "Aplicar" la guarda para la imagen (también
 * la usan la densidad y la clasificación IA) y "Descartar" vuelve a la guardada.
 *
 * Ref imperativa (para la paleta de comandos):
 * - toggle(): alterna la visibilidad de la máscara.
 * - show(): fuerza que la máscara se muestre.
 */
const TissueMaskControl = forwardRef(({ viewer, imageId }, ref) => {
  const [enabled, setEnabled] = useState(false);
  const [opacity, setOpacity] = useState(0.5);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  // Umbral: factor guardado (`savedFactor`) y el del deslizador (`factor`).
  const [savedFactor, setSavedFactor] = useState(1);
  const [factor, setFactor] = useState(1);
  const [preview, setPreview] = useState(null); // { tissuePercent } o null
  const [previewLoading, setPreviewLoading] = useState(false);

  const maskItemRef = useRef(null);
  const objectUrlRef = useRef(null);
  const previewTimerRef = useRef(null);
  const previewSeqRef = useRef(0);

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

  const applyStats = useCallback(data => {
    setStats(data);
    const stored = Number(data?.threshold_factor ?? 1);
    setSavedFactor(stored);
    setFactor(stored);
    setPreview(null);
  }, []);

  const addOverlay = useCallback(async () => {
    if (!viewer) return;
    setLoading(true);
    setError(null);
    try {
      const [statData, url] = await Promise.all([
        tissueService.getStats(imageId),
        tissueService.getMaskObjectUrl(imageId),
      ]);
      applyStats(statData.result_data || null);
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
  }, [viewer, imageId, showMask, applyStats]);

  // Cancela una vista previa pendiente al desmontar.
  useEffect(
    () => () => {
      if (previewTimerRef.current) clearTimeout(previewTimerRef.current);
    },
    []
  );

  /** Invalida cualquier vista previa programada o en curso. */
  const cancelPreview = () => {
    if (previewTimerRef.current) clearTimeout(previewTimerRef.current);
    previewSeqRef.current += 1;
    setPreviewLoading(false);
  };

  const requestPreview = useCallback(
    value => {
      if (previewTimerRef.current) clearTimeout(previewTimerRef.current);
      previewTimerRef.current = setTimeout(async () => {
        const seq = ++previewSeqRef.current;
        setPreviewLoading(true);
        setError(null);
        try {
          const result = await tissueService.getPreview(imageId, value);
          if (seq !== previewSeqRef.current) {
            URL.revokeObjectURL(result.url); // respuesta antigua: se descarta
            return;
          }
          removeOverlay();
          objectUrlRef.current = result.url;
          showMask(result.url);
          setPreview({ tissuePercent: result.tissuePercent });
        } catch (err) {
          if (seq === previewSeqRef.current) {
            setError(err.message || 'Error en la vista previa');
          }
        } finally {
          if (seq === previewSeqRef.current) setPreviewLoading(false);
        }
      }, 250);
    },
    [imageId, removeOverlay, showMask]
  );

  const handleFactorChange = value => {
    setFactor(value);
    requestPreview(value);
  };

  const reloadSaved = useCallback(async () => {
    const [statData, url] = await Promise.all([
      tissueService.getStats(imageId),
      tissueService.getMaskObjectUrl(imageId),
    ]);
    removeOverlay();
    applyStats(statData.result_data || null);
    objectUrlRef.current = url;
    showMask(url);
  }, [imageId, removeOverlay, applyStats, showMask]);

  const handleApplyFactor = async () => {
    cancelPreview();
    setLoading(true);
    setError(null);
    try {
      await tissueService.analyze(imageId, { thresholdFactor: factor });
      await reloadSaved();
    } catch (err) {
      setError(err.message || 'Error al aplicar el umbral');
    } finally {
      setLoading(false);
    }
  };

  const handleDiscardPreview = async () => {
    cancelPreview();
    setLoading(true);
    setError(null);
    try {
      await reloadSaved();
    } catch (err) {
      setError(err.message || 'Error al restaurar la máscara');
    } finally {
      setLoading(false);
    }
  };

  const factorChanged = Math.abs(factor - savedFactor) > 1e-6;

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    if (next) {
      addOverlay();
    } else {
      cancelPreview();
      setFactor(savedFactor);
      setPreview(null);
      removeOverlay();
    }
  };

  // Permite alternar la máscara desde fuera (p. ej. la paleta de comandos).
  const toggleRef = useRef(handleToggle);
  toggleRef.current = handleToggle;

  // Fuerza que la máscara se muestre (tras ejecutarla desde la paleta).
  const ensureShown = useCallback(() => {
    setEnabled(true);
    removeOverlay();
    addOverlay();
  }, [removeOverlay, addOverlay]);
  const showRef = useRef(ensureShown);
  showRef.current = ensureShown;

  // Expone métodos imperativos estables que invocan siempre el último
  // manejador; la paleta de comandos los llama directamente y de forma
  // síncrona, sin depender de efectos ni de re-renders del contenedor.
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
      applyStats(statData.result_data || null);
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

      {enabled && stats && (
        <div className="tissue-threshold">
          <div className="tissue-threshold-head">
            <label htmlFor="tissue-threshold">
              <SlidersHorizontal size={13} /> Umbral de detección
            </label>
            <span className="tissue-threshold-value">
              ×{factor.toFixed(2)}
              {Math.abs(factor - 1) < 1e-6 ? ' (automático)' : ''}
            </span>
          </div>
          <input
            id="tissue-threshold"
            type="range"
            min="0.25"
            max="3"
            step="0.05"
            value={factor}
            onChange={e => handleFactorChange(Number(e.target.value))}
            disabled={loading}
          />
          <div className="tissue-threshold-scale" aria-hidden="true">
            <span>Más tejido</span>
            <span>Menos tejido</span>
          </div>
          {factorChanged && (
            <div className="tissue-threshold-preview" role="status">
              {previewLoading ? (
                <span>
                  <Loader2 size={12} className="tissue-spin" /> Calculando vista previa…
                </span>
              ) : (
                <span>
                  Vista previa:{' '}
                  <strong>
                    {preview?.tissuePercent != null
                      ? `${preview.tissuePercent.toFixed(1)}%`
                      : '—'}
                  </strong>{' '}
                  de tejido (sin guardar)
                </span>
              )}
              <div className="tissue-threshold-actions">
                <button
                  type="button"
                  className="tissue-threshold-discard"
                  onClick={handleDiscardPreview}
                  disabled={loading}
                >
                  Descartar
                </button>
                <button
                  type="button"
                  className="tissue-threshold-apply"
                  onClick={handleApplyFactor}
                  disabled={loading || previewLoading}
                  title="Guarda el umbral para esta imagen; también lo usan el mapa de densidad y la clasificación IA"
                >
                  Aplicar
                </button>
              </div>
            </div>
          )}
          {!factorChanged && Math.abs(savedFactor - 1) > 1e-6 && (
            <button
              type="button"
              className="tissue-threshold-reset"
              onClick={() => handleFactorChange(1)}
              disabled={loading}
            >
              Volver al umbral automático
            </button>
          )}
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
});

TissueMaskControl.displayName = 'TissueMaskControl';

export default TissueMaskControl;
