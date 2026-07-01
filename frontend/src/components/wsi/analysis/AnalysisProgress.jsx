import { Loader2, X, Clock } from 'lucide-react';
import './AnalysisProgress.css';

/**
 * Indicador de progreso del análisis (issue 42).
 *
 * El backend resuelve el análisis en una única petición, por lo que el progreso
 * se estima en el cliente mientras la petición está en curso. Muestra barra,
 * porcentaje, tiempo transcurrido y estimación restante, con opción de cancelar.
 *
 * Props:
 * - progress: número 0-100
 * - elapsedMs: milisegundos transcurridos
 * - onCancel: callback para cancelar el análisis
 */
const formatSeconds = ms => {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
};

const AnalysisProgress = ({ progress, elapsedMs, onCancel }) => {
  const pct = Math.min(100, Math.max(0, Math.round(progress)));
  const etaMs =
    progress > 3 ? (elapsedMs / progress) * (100 - progress) : null;

  return (
    <div className="analysis-progress">
      <div className="analysis-progress-top">
        <span className="analysis-progress-label">
          <Loader2 size={14} className="analysis-spin" /> Analizando…
        </span>
        <span className="analysis-progress-pct">{pct}%</span>
      </div>

      <div className="analysis-progress-bar">
        <div
          className="analysis-progress-fill"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>

      <div className="analysis-progress-meta">
        <span>
          <Clock size={12} /> {formatSeconds(elapsedMs)} transcurrido
        </span>
        {etaMs != null && <span>~{formatSeconds(etaMs)} restante</span>}
      </div>

      <button
        type="button"
        className="analysis-progress-cancel"
        onClick={onCancel}
      >
        <X size={13} /> Cancelar
      </button>
    </div>
  );
};

export default AnalysisProgress;
