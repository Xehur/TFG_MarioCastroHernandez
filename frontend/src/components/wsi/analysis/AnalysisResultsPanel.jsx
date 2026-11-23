import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  Play,
  RefreshCw,
  AlertCircle,
  Layers,
  Percent,
  CalendarClock,
} from 'lucide-react';
import { analysisService } from '../../../services/analysisService';
import AnalysisProgress from './AnalysisProgress';
import './AnalysisResultsPanel.css';

const PROGRESS_TICK_MS = 200;

/**
 * Panel de resultados de análisis (issues 41, 42).
 *
 * Lanza el análisis consolidado (tejido + densidad), muestra un indicador de
 * progreso mientras se ejecuta (con cancelación) y presenta las métricas
 * resultantes: % de tejido, densidad media/máx, tamaño de grid y fecha.
 *
 * Props:
 * - imageId: id de la imagen
 * - gridSize / colormap: parámetros del análisis (opcionales)
 */
const AnalysisResultsPanel = ({ imageId, gridSize = 256, colormap = 'viridis' }) => {
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | running | error
  const [progress, setProgress] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [error, setError] = useState(null);

  const abortRef = useRef(null);
  const intervalRef = useRef(null);
  const startRef = useRef(0);

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    let active = true;
    analysisService
      .getAnalysis(imageId)
      .then(data => {
        if (active && data) setSummary(data.result_data || null);
      })
      .catch(() => {});
    return () => {
      active = false;
      clearTimer();
      if (abortRef.current) abortRef.current.abort();
    };
  }, [imageId, clearTimer]);

  const startAnalysis = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    startRef.current = Date.now();
    setStatus('running');
    setError(null);
    setProgress(0);
    setElapsedMs(0);

    clearTimer();
    intervalRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startRef.current);
      // Aproximación asintótica hacia el 90% mientras dura la petición.
      setProgress(p => Math.min(90, p + (90 - p) * 0.08 + 1));
    }, PROGRESS_TICK_MS);

    try {
      const data = await analysisService.runAnalysis(imageId, {
        gridSize,
        colormap,
        signal: controller.signal,
      });
      clearTimer();
      setProgress(100);
      setSummary(data.result_data || null);
      setStatus('idle');
    } catch (err) {
      clearTimer();
      if (controller.signal.aborted) {
        setStatus('idle');
        setProgress(0);
        return;
      }
      setError(
        err.response?.data?.detail || err.message || 'Error durante el análisis'
      );
      setStatus('error');
    } finally {
      abortRef.current = null;
    }
  }, [imageId, gridSize, colormap, clearTimer]);

  const handleCancel = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    clearTimer();
    setStatus('idle');
    setProgress(0);
  }, [clearTimer]);

  const tissuePct = summary?.tissue?.tissue_percent;
  const densityStd = summary?.density?.density_std;
  const densityMax = summary?.density?.density_max;
  const analyzedAt = summary?.analyzed_at;

  return (
    <div className="results-panel">
      <div className="results-panel-header">
        <Activity size={16} />
        <span>Resultados de análisis</span>
      </div>

      {status === 'running' ? (
        <AnalysisProgress
          progress={progress}
          elapsedMs={elapsedMs}
          onCancel={handleCancel}
        />
      ) : (
        <>
          {summary ? (
            <div className="results-grid">
              <div className="result-card">
                <span className="result-card-label">
                  <Percent size={13} /> Tejido
                </span>
                <span className="result-card-value">
                  {tissuePct != null ? `${tissuePct.toFixed(1)}%` : '—'}
                </span>
              </div>
              <div className="result-card">
                <span className="result-card-label">
                  <Activity size={13} /> Densidad máx
                </span>
                <span className="result-card-value">
                  {densityMax != null
                    ? `${(densityMax * 100).toFixed(1)}%`
                    : '—'}
                </span>
              </div>
              <div className="result-card">
                <span className="result-card-label">
                  <Activity size={13} /> Variabilidad
                </span>
                <span
                  className="result-card-value"
                  title="Desviación típica de la densidad entre zonas: alta = tejido concentrado en focos; baja = distribución uniforme"
                >
                  {densityStd != null
                    ? `${(densityStd * 100).toFixed(1)}%`
                    : '—'}
                </span>
              </div>
              <div className="result-card">
                <span className="result-card-label">
                  <Layers size={13} /> Grid
                </span>
                <span className="result-card-value">
                  {summary?.density?.grid_size ?? '—'} px
                </span>
              </div>
              {analyzedAt && (
                <div className="result-date">
                  <CalendarClock size={13} />{' '}
                  {new Date(analyzedAt).toLocaleString()}
                </div>
              )}
            </div>
          ) : (
            <p className="results-empty">
              Esta imagen aún no se ha analizado.
            </p>
          )}

          <button
            type="button"
            className="results-analyze-btn"
            onClick={startAnalysis}
          >
            {summary ? (
              <>
                <RefreshCw size={15} /> Re-analizar
              </>
            ) : (
              <>
                <Play size={15} /> Analizar imagen
              </>
            )}
          </button>
        </>
      )}

      {error && (
        <p className="results-error">
          <AlertCircle size={14} /> {error}
        </p>
      )}
    </div>
  );
};

export default AnalysisResultsPanel;
