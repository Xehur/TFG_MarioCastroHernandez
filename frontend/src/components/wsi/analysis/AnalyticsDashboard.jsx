import { useState, useEffect, useCallback, useRef } from 'react';
import {
  BarChart3,
  PieChart as PieIcon,
  Activity,
  Layers,
  Brain,
  Info,
  AlertCircle,
  Loader2,
  RefreshCw,
  Download,
  X,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { analyticsService } from '../../../services/analyticsService';
import { annotationAnalysisService } from '../../../services/annotationAnalysisService';
import { aiClassificationService } from '../../../services/aiClassificationService';
import './AnalyticsDashboard.css';

const CHART_COLORS = [
  '#8e2de2',
  '#b24592',
  '#cf8fd8',
  '#6b3fa0',
  '#e07bb8',
  '#9333ea',
  '#c026d3',
  '#7c3aed',
];

// Orden de lectura de las clases IA (de menor a mayor gravedad histológica).
const AI_ORDER = ['NORMAL', 'BENIGN', 'INSITU', 'INVASIVE'];
const DENSITY_COLORS = { Baja: '#e9d5ff', Media: '#c084fc', Alta: '#7e22ce' };

const nf = (value, digits = 1) =>
  Number(value).toLocaleString('es-ES', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });

/** Superficie legible: "12,5 mm²", "< 0,01 mm²" o "—". */
export const formatArea = mm2 => {
  if (mm2 == null) return '—';
  if (mm2 > 0 && mm2 < 0.01) return '< 0,01 mm²';
  return `${nf(mm2, mm2 < 10 ? 2 : 1)} mm²`;
};

/** [ancho, alto] en µm -> "860×645 µm" (o "—"). */
const formatMicrons = dims =>
  Array.isArray(dims) && dims.length === 2
    ? `${dims.map(v => Math.round(v)).join('×')} µm`
    : '—';

const formatPercent = (value, digits = 1) =>
  value == null ? '—' : `${nf(value, digits)} %`;

/** Serializa el SVG de un contenedor y lo descarga como SVG o PNG. */
const exportChart = (container, filename, format) => {
  if (!container) return;
  const svg = container.querySelector('svg');
  if (!svg) return;

  const clone = svg.cloneNode(true);
  const rect = svg.getBoundingClientRect();
  const width = Math.round(rect.width) || 600;
  const height = Math.round(rect.height) || 300;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', width);
  clone.setAttribute('height', height);
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('width', width);
  bg.setAttribute('height', height);
  bg.setAttribute('fill', '#ffffff');
  clone.insertBefore(bg, clone.firstChild);

  const source = new XMLSerializer().serializeToString(clone);
  const svgBlob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });

  if (format === 'svg') {
    const url = URL.createObjectURL(svgBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.svg`;
    a.click();
    URL.revokeObjectURL(url);
    return;
  }

  const url = URL.createObjectURL(svgBlob);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    canvas.toBlob(blob => {
      if (!blob) return;
      const pngUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = pngUrl;
      a.download = `${filename}.png`;
      a.click();
      URL.revokeObjectURL(pngUrl);
    }, 'image/png');
  };
  img.src = url;
};

/** Tarjeta con título y, opcionalmente, botones de exportación. */
const ChartCard = ({ icon: Icon, title, exportName, chartRef, children }) => (
  <div className="analytics-card">
    <div className="analytics-card-header">
      <span className="analytics-card-title">
        <Icon size={15} /> {title}
      </span>
      {exportName && (
        <span className="analytics-export">
          <button
            type="button"
            title="Exportar PNG"
            onClick={() => exportChart(chartRef.current, exportName, 'png')}
          >
            <Download size={13} /> PNG
          </button>
          <button
            type="button"
            title="Exportar SVG"
            onClick={() => exportChart(chartRef.current, exportName, 'svg')}
          >
            <Download size={13} /> SVG
          </button>
        </span>
      )}
    </div>
    <div className="analytics-card-body" ref={chartRef}>
      {children}
    </div>
  </div>
);

/** Indicador del resumen superior. */
const Stat = ({ value, label, sub }) => (
  <div className="analytics-stat">
    <span className="analytics-stat-value">{value}</span>
    <span className="analytics-stat-label">{label}</span>
    {sub && <span className="analytics-stat-sub">{sub}</span>}
  </div>
);

/**
 * Dashboard de análisis de una imagen (o de una región anotada).
 *
 * Presenta métricas fáciles de interpretar: superficie de tejido en mm² y nº
 * de fragmentos, resultado de la clasificación IA (clase predominante,
 * proporción con patrón de carcinoma y reparto por clase), reparto de la
 * densidad de tejido en niveles bajo/medio/alto, anotaciones por clase con su
 * área e información física de la imagen. Las gráficas se exportan a PNG/SVG.
 *
 * Props:
 * - imageId: id de la imagen (analíticas de la imagen completa)
 * - annotationId: si se indica, muestra las analíticas de esa anotación
 *   (zona marcada) "como si fuese una WSI aparte".
 * - onClose(): cierra el dashboard
 */
const AnalyticsDashboard = ({ imageId, annotationId, onClose }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);

  const isAnnotation = annotationId != null;

  const aiRef = useRef(null);
  const densityRef = useRef(null);
  const fragmentsRef = useRef(null);
  const classRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isAnnotation) {
        let result = await annotationAnalysisService.getAnalytics(annotationId);
        // Si la región aún no tiene análisis, lánzalo y vuelve a pedir.
        if (!result.tissue) {
          await annotationAnalysisService.runAnalysis(annotationId);
          result = await annotationAnalysisService.getAnalytics(annotationId);
        }
        setData(result);
      } else {
        setData(await analyticsService.getAnalytics(imageId));
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Error cargando analíticas'
      );
    } finally {
      setLoading(false);
    }
  }, [imageId, annotationId, isAnnotation]);

  useEffect(() => {
    load();
  }, [load]);

  const runAiClassification = useCallback(async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      if (isAnnotation) {
        await aiClassificationService.analyzeAnnotation(annotationId);
      } else {
        await aiClassificationService.analyze(imageId);
      }
      await load();
    } catch (err) {
      setAiError(
        err.response?.data?.detail ||
          err.message ||
          'Error en la clasificación IA'
      );
    } finally {
      setAiLoading(false);
    }
  }, [isAnnotation, annotationId, imageId, load]);

  const ai = data?.ai;
  const tissue = data?.tissue;
  const info = data?.image_info;

  const aiClasses = ai
    ? [...(ai.classes || [])].sort(
        (a, b) => AI_ORDER.indexOf(a.code) - AI_ORDER.indexOf(b.code)
      )
    : [];
  const aiChartData = aiClasses.map(c => ({
    name: c.name,
    percent: c.percent,
    fill: `rgb(${(c.color || [148, 163, 184]).join(',')})`,
  }));

  const densityData = (data?.density_levels?.levels || []).map(l => ({
    name: `${l.level} (${l.range})`,
    level: l.level,
    percent: l.percent,
  }));

  const fragmentData = (tissue?.fragment_areas_mm2 || []).map((area, i) => ({
    name: `F${i + 1}`,
    area,
  }));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-card analytics-modal"
        onClick={e => e.stopPropagation()}
      >
        <div className="analytics-modal-head">
          <h2>
            <BarChart3 size={20} />{' '}
            {isAnnotation
              ? `Dashboard de anotación #${annotationId}`
              : 'Dashboard de análisis'}
          </h2>
          <div className="analytics-controls">
            <button
              type="button"
              className="analytics-refresh"
              onClick={load}
              title="Actualizar"
            >
              <RefreshCw size={15} />
            </button>
            <button
              type="button"
              className="analytics-close"
              onClick={onClose}
              title="Cerrar"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {loading && !data && (
          <p className="analytics-loading">
            <Loader2 size={18} className="analytics-spin" /> Cargando
            analíticas…
          </p>
        )}

        {error && (
          <p className="analytics-error">
            <AlertCircle size={16} /> {error}
          </p>
        )}

        {!error && data && (
          <div className="analytics-body">
            {isAnnotation && (
              <p className="analytics-caption analytics-region-note">
                Análisis de la región marcada (anotación #{annotationId})
                tratada como una imagen independiente.
              </p>
            )}

            <div className="analytics-summary">
              <Stat
                value={
                  tissue?.area_mm2 != null
                    ? formatArea(tissue.area_mm2)
                    : formatPercent(tissue?.tissue_percent)
                }
                label="Tejido"
                sub={
                  tissue?.area_mm2 != null && tissue?.tissue_percent != null
                    ? `${formatPercent(tissue.tissue_percent)} de la ${
                        isAnnotation ? 'región' : 'imagen'
                      }`
                    : null
                }
              />
              <Stat
                value={tissue?.fragments ?? '—'}
                label="Fragmentos"
                sub="piezas de tejido separadas"
              />
              <Stat
                value={ai?.dominant_name || '—'}
                label="Predominante (IA)"
                sub={
                  ai?.dominant_percent != null
                    ? `${formatPercent(ai.dominant_percent, 0)} del tejido analizado`
                    : 'sin clasificar todavía'
                }
              />
              <Stat
                value={ai ? formatPercent(ai.carcinoma_percent, 0) : '—'}
                label="Patrón de carcinoma"
                sub="in situ + invasivo"
              />
              {isAnnotation ? (
                <Stat
                  value={formatArea(data.annotated_area_mm2)}
                  label="Área de la región"
                />
              ) : (
                <Stat
                  value={data.total_annotations}
                  label="Anotaciones"
                  sub={
                    data.annotated_area_mm2 != null
                      ? `${formatArea(data.annotated_area_mm2)} anotados`
                      : null
                  }
                />
              )}
            </div>

            <div className="analytics-grid">
              <ChartCard
                icon={Brain}
                title="Clasificación de tejido (IA)"
                exportName="clasificacion-ia"
                chartRef={aiRef}
              >
                {ai ? (
                  <>
                    <p className="analytics-caption">
                      Proporción de cada tipo de tejido en las zonas analizadas
                      {ai.cell_divisor > 1 ? (
                        <>
                          {' '}
                          ({ai.analyzed_fields} posiciones analizadas: campos de
                          ≈ {formatMicrons(ai.field_um)} desplazados cada ≈{' '}
                          {formatMicrons(ai.cell_um)})
                        </>
                      ) : (
                        <>
                          {' '}
                          ({ai.analyzed_fields} de {ai.tissue_fields} campos con
                          tejido
                          {ai.field_um ? `, de ≈ ${formatMicrons(ai.field_um)}` : ''})
                        </>
                      )}
                      . Confianza media del modelo:{' '}
                      <strong>
                        {ai.mean_confidence != null
                          ? formatPercent(ai.mean_confidence * 100, 0)
                          : '—'}
                      </strong>
                      .
                    </p>
                    <ResponsiveContainer width="100%" height={170}>
                      <BarChart
                        data={aiChartData}
                        layout="vertical"
                        margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis
                          type="number"
                          domain={[0, 100]}
                          unit="%"
                          fontSize={11}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={120}
                          fontSize={11}
                        />
                        <Tooltip
                          formatter={v => [formatPercent(v), 'Proporción']}
                        />
                        <Bar dataKey="percent" radius={[0, 6, 6, 0]}>
                          {aiChartData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                    <table className="analytics-table">
                      <thead>
                        <tr>
                          <th>Clase</th>
                          <th>Proporción</th>
                          <th title="Media de la probabilidad que el modelo asigna a cada clase en los campos analizados: refleja también el tejido mezclado dentro de cada campo">
                            Prob. media
                          </th>
                          <th>Superficie aprox.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {aiClasses.map(c => (
                          <tr key={c.code}>
                            <td>
                              <span
                                className="analytics-chip"
                                style={{
                                  background: `rgb(${(c.color || []).join(',')})`,
                                }}
                              />
                              {c.name}
                            </td>
                            <td>{formatPercent(c.percent)}</td>
                            <td>
                              {c.mean_probability != null
                                ? formatPercent(c.mean_probability * 100)
                                : '—'}
                            </td>
                            <td>{formatArea(c.area_mm2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {ai.field_exceeds_region && (
                      <p className="analytics-caption">
                        La zona es más pequeña que el campo con el que se
                        entrenó el modelo ({formatMicrons(ai.field_um)}): cada
                        clasificación incluye también tejido de su entorno.
                      </p>
                    )}
                    {ai.disclaimer && (
                      <p className="analytics-caption analytics-disclaimer">
                        {ai.disclaimer}
                      </p>
                    )}
                    <button
                      type="button"
                      className="analytics-ai-run"
                      onClick={runAiClassification}
                      disabled={aiLoading}
                    >
                      {aiLoading ? (
                        <Loader2 size={14} className="analytics-spin" />
                      ) : (
                        <RefreshCw size={14} />
                      )}
                      Re-clasificar
                    </button>
                  </>
                ) : aiLoading ? (
                  <p className="analytics-loading">
                    <Loader2 size={18} className="analytics-spin" />{' '}
                    Clasificando con IA…
                  </p>
                ) : (
                  <div className="analytics-ai-cta">
                    <p className="analytics-empty">
                      Clasifica el tejido mamario en Normal, Benigno, Carcinoma
                      in situ y Carcinoma invasivo con el modelo de IA.
                    </p>
                    <button
                      type="button"
                      className="analytics-ai-run"
                      onClick={runAiClassification}
                    >
                      <Brain size={15} /> Ejecutar clasificación IA
                    </button>
                  </div>
                )}
                {aiError && (
                  <p className="analytics-error">
                    <AlertCircle size={14} /> {aiError}
                  </p>
                )}
              </ChartCard>

              <ChartCard
                icon={Activity}
                title="Densidad del tejido"
                exportName="densidad-tejido"
                chartRef={densityRef}
              >
                {densityData.length ? (
                  <>
                    <p className="analytics-caption">
                      Cómo de compacto es el tejido: porcentaje de zonas con
                      tejido según su densidad. Densidad media:{' '}
                      <strong>
                        {formatPercent(data.density_levels.mean_percent, 0)}
                      </strong>
                      .
                    </p>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={densityData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis dataKey="name" fontSize={11} />
                        <YAxis fontSize={11} unit="%" domain={[0, 100]} />
                        <Tooltip
                          formatter={v => [formatPercent(v), 'Zonas']}
                        />
                        <Bar dataKey="percent" radius={[6, 6, 0, 0]}>
                          {densityData.map((d, i) => (
                            <Cell key={i} fill={DENSITY_COLORS[d.level]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </>
                ) : (
                  <p className="analytics-empty">
                    Genera un mapa de densidades para ver esta gráfica.
                  </p>
                )}
              </ChartCard>

              <ChartCard
                icon={Layers}
                title="Fragmentos de tejido"
                exportName="fragmentos-tejido"
                chartRef={fragmentsRef}
              >
                {fragmentData.length ? (
                  <>
                    <p className="analytics-caption">
                      Cada barra es una pieza de tejido separada (p. ej. un
                      cilindro de biopsia), ordenadas de mayor a menor
                      superficie
                      {tissue.fragments > fragmentData.length
                        ? ` (se muestran las ${fragmentData.length} mayores de ${tissue.fragments})`
                        : ''}
                      .
                    </p>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={fragmentData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis dataKey="name" fontSize={11} />
                        <YAxis fontSize={11} unit=" mm²" width={70} />
                        <Tooltip formatter={v => [formatArea(v), 'Superficie']} />
                        <Bar
                          dataKey="area"
                          fill="#b24592"
                          radius={[6, 6, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </>
                ) : tissue ? (
                  <p className="analytics-empty">
                    {tissue.fragments
                      ? `${tissue.fragments} fragmento(s) de tejido.`
                      : 'No se detectaron fragmentos de tejido.'}{' '}
                    Las superficies requieren la resolución física (µm/px) de
                    la imagen.
                  </p>
                ) : (
                  <p className="analytics-empty">
                    Analiza el tejido para ver sus fragmentos.
                  </p>
                )}
              </ChartCard>

              {!isAnnotation && (
                <ChartCard
                  icon={PieIcon}
                  title="Anotaciones por clase"
                  exportName="anotaciones-por-clase"
                  chartRef={classRef}
                >
                  {data.by_class?.length ? (
                    <>
                      <ResponsiveContainer width="100%" height={190}>
                        <PieChart>
                          <Pie
                            data={data.by_class}
                            dataKey="count"
                            nameKey="class"
                            cx="50%"
                            cy="50%"
                            outerRadius={65}
                          >
                            {data.by_class.map((entry, i) => (
                              <Cell
                                key={i}
                                fill={
                                  entry.color ||
                                  CHART_COLORS[i % CHART_COLORS.length]
                                }
                              />
                            ))}
                          </Pie>
                          <Tooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                      <table className="analytics-table">
                        <thead>
                          <tr>
                            <th>Clase</th>
                            <th>Nº</th>
                            <th>Área</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.by_class.map(row => (
                            <tr key={row.class}>
                              <td>{row.class}</td>
                              <td>{row.count}</td>
                              <td>{formatArea(row.area_mm2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </>
                  ) : (
                    <p className="analytics-empty">
                      Sin anotaciones. Dibuja zonas en el visor y asígnales una
                      clase para verlas aquí.
                    </p>
                  )}
                </ChartCard>
              )}

              <ChartCard
                icon={Info}
                title={isAnnotation ? 'Información de la región' : 'Información de la imagen'}
              >
                <table className="analytics-table">
                  <tbody>
                    <tr>
                      <td>Tamaño</td>
                      <td>
                        {info?.width_mm != null
                          ? `${nf(info.width_mm, 2)} × ${nf(info.height_mm, 2)} mm`
                          : '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>Píxeles</td>
                      <td>
                        {info
                          ? `${info.width_px.toLocaleString('es-ES')} × ${info.height_px.toLocaleString('es-ES')}`
                          : '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>Resolución</td>
                      <td>
                        {info?.mpp != null ? `${nf(info.mpp, 3)} µm/px` : '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>Aumento aprox.</td>
                      <td>
                        {info?.magnification != null
                          ? `${nf(info.magnification)}x`
                          : '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>Tejido detectado</td>
                      <td>{formatPercent(tissue?.tissue_percent)}</td>
                    </tr>
                  </tbody>
                </table>
              </ChartCard>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
