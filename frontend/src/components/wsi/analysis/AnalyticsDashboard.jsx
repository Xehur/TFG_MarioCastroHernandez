import { useState, useEffect, useCallback, useRef } from 'react';
import {
  BarChart3,
  PieChart as PieIcon,
  Grid3x3,
  Activity,
  Layers,
  Brain,
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
  LineChart,
  Line,
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

/** Cabecera de sección con título y botones de exportación. */
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

/** Heatmap simple de distribución espacial (rejilla de celdas). */
const SpatialHeatmap = ({ spatial }) => {
  const { grid = [], max = 0, bins = 0 } = spatial || {};
  if (!bins) return <p className="analytics-empty">Sin datos espaciales.</p>;
  return (
    <div
      className="analytics-heatmap"
      style={{ gridTemplateColumns: `repeat(${bins}, 1fr)` }}
    >
      {grid.map((row, r) =>
        row.map((count, c) => {
          const intensity = max > 0 ? count / max : 0;
          return (
            <div
              key={`${r}-${c}`}
              className="analytics-heatmap-cell"
              title={`Celda [${r}, ${c}]: ${count} anotación(es)`}
              style={{
                background:
                  count > 0
                    ? `rgba(142, 45, 226, ${0.15 + intensity * 0.85})`
                    : 'rgba(178, 69, 146, 0.06)',
              }}
            >
              {count > 0 ? count : ''}
            </div>
          );
        })
      )}
    </div>
  );
};

/**
 * Dashboard de gráficas y tablas interactivas (issue 49).
 *
 * Muestra la distribución de anotaciones (barras/tarta/tabla), la distribución
 * espacial (heatmap), las estadísticas de tejido y la densidad por zonas
 * (líneas + histograma). Permite ajustar la resolución espacial y exportar
 * cada gráfica a PNG/SVG.
 *
 * Props:
 * - imageId: id de la imagen (analíticas de la imagen completa)
 * - annotationId: si se indica, muestra las analíticas de esa anotación
 *   (zona marcada) "como si fuese una WSI aparte". Tiene prioridad sobre
 *   imageId para la fuente de datos.
 * - onClose(): cierra el dashboard
 */
const AnalyticsDashboard = ({ imageId, annotationId, onClose }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [spatialBins, setSpatialBins] = useState(10);

  const [aiData, setAiData] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);

  const isAnnotation = annotationId != null;

  const typeRef = useRef(null);
  const classRef = useRef(null);
  const densityLineRef = useRef(null);
  const histRef = useRef(null);
  const aiRef = useRef(null);

  // Reinicia la clasificación IA al cambiar de ámbito (imagen o anotación).
  useEffect(() => {
    setAiData(null);
    setAiError(null);
  }, [imageId, annotationId]);

  const runAiClassification = useCallback(async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const res = isAnnotation
        ? await aiClassificationService.analyzeAnnotation(annotationId)
        : await aiClassificationService.analyze(imageId);
      setAiData(res.result_data || null);
    } catch (err) {
      setAiError(
        err.response?.data?.detail ||
          err.message ||
          'Error en la clasificación IA'
      );
    } finally {
      setAiLoading(false);
    }
  }, [isAnnotation, annotationId, imageId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isAnnotation) {
        let result = await annotationAnalysisService.getAnalytics(
          annotationId,
          { spatialBins }
        );
        // Si la región aún no tiene análisis, lánzalo y vuelve a pedir.
        if (!result.tissue) {
          await annotationAnalysisService.runAnalysis(annotationId);
          result = await annotationAnalysisService.getAnalytics(annotationId, {
            spatialBins,
          });
        }
        setData(result);
      } else {
        const result = await analyticsService.getAnalytics(imageId, {
          spatialBins,
        });
        setData(result);
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
  }, [imageId, annotationId, isAnnotation, spatialBins]);

  useEffect(() => {
    load();
  }, [load]);

  const densityLineData = data?.density_zones
    ? (data.density_zones.row_means || []).map((v, i) => ({
        zona: i + 1,
        fila: v,
        columna: data.density_zones.col_means?.[i] ?? null,
      }))
    : [];

  const histData = data?.density_zones?.histogram
    ? data.density_zones.histogram.counts.map((count, i) => ({
        rango: `${Math.round(
          (data.density_zones.histogram.edges[i] || 0) * 100
        )}%`,
        count,
      }))
    : [];

  const aiGroupData = (aiData?.groups || [])
    .filter(g => g.percent > 0)
    .map(g => ({
      group: g.group,
      percent: g.percent,
      fill: `rgb(${g.color.join(',')})`,
    }));
  const aiDominant = aiData?.classes?.find(
    c => c.code === aiData.dominant_class
  );

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
            <label className="analytics-filter">
              Resolución espacial
              <select
                value={spatialBins}
                onChange={e => setSpatialBins(Number(e.target.value))}
              >
                <option value={5}>5 x 5</option>
                <option value={10}>10 x 10</option>
                <option value={15}>15 x 15</option>
                <option value={20}>20 x 20</option>
              </select>
            </label>
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

        {loading && (
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

        {!loading && !error && data && (
          <div className="analytics-body">
            {isAnnotation && (
              <p className="analytics-caption analytics-region-note">
                Análisis de la región marcada (anotación #{annotationId})
                tratada como una imagen independiente. Las gráficas de
                anotaciones no aplican aquí; céntrate en el tejido y la densidad
                por zonas.
              </p>
            )}
            <div className="analytics-summary">
              <div className="analytics-stat">
                <span className="analytics-stat-value">
                  {data.total_annotations}
                </span>
                <span className="analytics-stat-label">Anotaciones</span>
              </div>
              <div className="analytics-stat">
                <span className="analytics-stat-value">
                  {data.by_class?.length || 0}
                </span>
                <span className="analytics-stat-label">Clasificaciones</span>
              </div>
              <div className="analytics-stat">
                <span className="analytics-stat-value">
                  {data.tissue?.tissue_percent != null
                    ? `${data.tissue.tissue_percent.toFixed(1)}%`
                    : '—'}
                </span>
                <span className="analytics-stat-label">Tejido</span>
              </div>
            </div>

            <div className="analytics-grid">
              <ChartCard
                icon={Brain}
                title="Clasificación de tejido (IA)"
                exportName="clasificacion-ia"
                chartRef={aiRef}
              >
                {aiData ? (
                  <>
                    <p className="analytics-caption">
                      Modelo {aiData.model?.dataset || 'IA'}. Clase predominante:{' '}
                      <strong>{aiDominant ? aiDominant.name : '—'}</strong>
                      {aiData.dominant_group
                        ? ` (${aiData.dominant_group})`
                        : ''}
                      .
                    </p>
                    {aiGroupData.length ? (
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={aiGroupData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                          <XAxis dataKey="group" fontSize={12} />
                          <YAxis
                            fontSize={12}
                            unit="%"
                            domain={[0, 100]}
                          />
                          <Tooltip
                            formatter={v => [`${v.toFixed(1)}%`, 'Proporción']}
                          />
                          <Bar dataKey="percent" radius={[6, 6, 0, 0]}>
                            {aiGroupData.map((entry, i) => (
                              <Cell key={i} fill={entry.fill} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="analytics-empty">
                        El modelo no detectó tejido clasificable en la región.
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
                    <Loader2 size={18} className="analytics-spin" /> Clasificando
                    con IA…
                  </p>
                ) : (
                  <div className="analytics-ai-cta">
                    <p className="analytics-empty">
                      Clasifica el tejido en categorías histológicas (tumoral,
                      estroma, no tumoral, necrosis) con un modelo de IA.
                    </p>
                    <button
                      type="button"
                      className="analytics-ai-run"
                      onClick={runAiClassification}
                    >
                      <Brain size={15} /> Ejecutar clasificación IA
                    </button>
                    {aiError && (
                      <p className="analytics-error">
                        <AlertCircle size={14} /> {aiError}
                      </p>
                    )}
                  </div>
                )}
              </ChartCard>

              {!isAnnotation && (
                <ChartCard
                  icon={BarChart3}
                  title="Anotaciones por tipo"
                  exportName="anotaciones-por-tipo"
                  chartRef={typeRef}
                >
                  {data.by_type?.length ? (
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={data.by_type}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis dataKey="type" fontSize={12} />
                        <YAxis allowDecimals={false} fontSize={12} />
                        <Tooltip />
                        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                          {data.by_type.map((_, i) => (
                            <Cell
                              key={i}
                              fill={CHART_COLORS[i % CHART_COLORS.length]}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="analytics-empty">Sin anotaciones.</p>
                  )}
                </ChartCard>
              )}

              {!isAnnotation && (
                <ChartCard
                  icon={PieIcon}
                  title="Anotaciones por clasificación"
                  exportName="anotaciones-por-clase"
                  chartRef={classRef}
                >
                  {data.by_class?.length ? (
                    <ResponsiveContainer width="100%" height={220}>
                      <PieChart>
                        <Pie
                          data={data.by_class}
                          dataKey="count"
                          nameKey="class"
                          cx="50%"
                          cy="50%"
                          outerRadius={70}
                          label={entry => entry.class}
                        >
                          {data.by_class.map((entry, i) => (
                            <Cell
                            key={i}
                            fill={
                              entry.color || CHART_COLORS[i % CHART_COLORS.length]
                            }
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="analytics-empty">Sin clasificaciones.</p>
                )}
                </ChartCard>
              )}

              <ChartCard
                icon={Grid3x3}
                title="Distribución espacial"
              >
                <SpatialHeatmap spatial={data.spatial} />
              </ChartCard>

              <ChartCard
                icon={Activity}
                title="Densidad de tejido por zonas"
                exportName="densidad-por-zonas"
                chartRef={densityLineRef}
              >
                {densityLineData.length ? (
                  <>
                    <p className="analytics-caption">
                      Densidad media de tejido a lo largo de la imagen: cada
                      punto es una franja. La línea horizontal recorre la imagen
                      de arriba abajo y la vertical de izquierda a derecha, para
                      ver dónde se concentra el tejido.
                    </p>
                    <ResponsiveContainer width="100%" height={220}>
                      <LineChart
                        data={densityLineData}
                        margin={{ top: 5, right: 10, bottom: 22, left: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                        <XAxis
                          dataKey="zona"
                          fontSize={12}
                          label={{
                            value: 'Franja (posición en la imagen)',
                            position: 'insideBottom',
                            offset: -12,
                            fontSize: 11,
                            fill: '#8d7ba3',
                          }}
                        />
                        <YAxis
                          fontSize={12}
                          domain={[0, 1]}
                          tickFormatter={v => `${Math.round(v * 100)}%`}
                          label={{
                            value: '% densidad',
                            angle: -90,
                            position: 'insideLeft',
                            fontSize: 11,
                            fill: '#8d7ba3',
                          }}
                        />
                        <Tooltip
                          formatter={v => `${(v * 100).toFixed(1)}%`}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="fila"
                          stroke="#8e2de2"
                          strokeWidth={2}
                          dot={false}
                          name="Franjas horizontales (arriba → abajo)"
                        />
                        <Line
                          type="monotone"
                          dataKey="columna"
                          stroke="#e07bb8"
                          strokeWidth={2}
                          dot={false}
                          name="Franjas verticales (izquierda → derecha)"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </>
                ) : (
                  <p className="analytics-empty">
                    Genera un mapa de densidades para ver esta gráfica.
                  </p>
                )}
              </ChartCard>

              <ChartCard
                icon={BarChart3}
                title="Histograma de densidad"
                exportName="histograma-densidad"
                chartRef={histRef}
              >
                {histData.length ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={histData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                      <XAxis dataKey="rango" fontSize={11} />
                      <YAxis allowDecimals={false} fontSize={12} />
                      <Tooltip />
                      <Bar
                        dataKey="count"
                        fill="#b24592"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="analytics-empty">
                    Genera un mapa de densidades para ver el histograma.
                  </p>
                )}
              </ChartCard>

              <ChartCard icon={Layers} title="Estadísticas de tejido">
                {data.tissue ? (
                  <table className="analytics-table">
                    <tbody>
                      <tr>
                        <td>% Tejido</td>
                        <td>
                          {data.tissue.tissue_percent != null
                            ? `${data.tissue.tissue_percent.toFixed(2)}%`
                            : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td>Dimensiones</td>
                        <td>
                          {data.tissue.width} x {data.tissue.height} px
                        </td>
                      </tr>
                      <tr>
                        <td>Metodo</td>
                        <td>{data.tissue.method || '—'}</td>
                      </tr>
                      {data.density_zones && (
                        <>
                          <tr>
                            <td>Densidad máx</td>
                            <td>
                              {(
                                (data.density_zones.density_max || 0) * 100
                              ).toFixed(1)}
                              %
                            </td>
                          </tr>
                          <tr>
                            <td>Variabilidad</td>
                            <td>
                              {(
                                (data.density_zones.density_std || 0) * 100
                              ).toFixed(1)}
                              %
                            </td>
                          </tr>
                        </>
                      )}
                    </tbody>
                  </table>
                ) : (
                  <p className="analytics-empty">
                    Analiza el tejido para ver estas estadísticas.
                  </p>
                )}
              </ChartCard>

              <ChartCard
                icon={Grid3x3}
                title="Distribución de anotaciones"
              >
                {data.distribution?.length ? (
                  <table className="analytics-table">
                    <thead>
                      <tr>
                        <th>Tipo</th>
                        <th>Clasificación</th>
                        <th>Nº</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.distribution.map((row, i) => (
                        <tr key={i}>
                          <td>{row.type}</td>
                          <td>{row.class}</td>
                          <td>{row.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="analytics-empty">Sin datos.</p>
                )}
              </ChartCard>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
