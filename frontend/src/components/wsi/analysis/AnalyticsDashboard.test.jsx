import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../services/analyticsService', () => ({
  analyticsService: {
    getAnalytics: vi.fn(),
  },
}));

// Recharts depende de ResizeObserver/SVG real; se sustituye por stubs simples.
vi.mock('recharts', () => {
  const Stub = ({ children }) => <div>{children}</div>;
  return {
    ResponsiveContainer: Stub,
    BarChart: Stub,
    Bar: Stub,
    PieChart: Stub,
    Pie: Stub,
    Cell: Stub,
    LineChart: Stub,
    Line: Stub,
    XAxis: Stub,
    YAxis: Stub,
    CartesianGrid: Stub,
    Tooltip: Stub,
    Legend: Stub,
  };
});

import { analyticsService } from '../../../services/analyticsService';
import AnalyticsDashboard from './AnalyticsDashboard';

const DATA = {
  image_id: 1,
  total_annotations: 5,
  by_type: [
    { type: 'rectangle', count: 3 },
    { type: 'circle', count: 2 },
  ],
  by_class: [
    { class: 'Tumor', count: 3, color: '#ff0000' },
    { class: 'Sin clasificar', count: 2, color: '#9ca3af' },
  ],
  distribution: [
    { type: 'rectangle', class: 'Tumor', count: 3 },
    { type: 'circle', class: 'Sin clasificar', count: 2 },
  ],
  spatial: {
    bins: 2,
    width: 100,
    height: 100,
    grid: [
      [1, 0],
      [2, 2],
    ],
    max: 2,
  },
  tissue: {
    tissue_percent: 42.5,
    width: 200,
    height: 200,
    method: 'otsu',
  },
  density_zones: {
    grid_size: 256,
    colormap: 'viridis',
    rows: 2,
    cols: 2,
    row_means: [0.2, 0.6],
    col_means: [0.3, 0.5],
    density_mean: 0.4,
    density_max: 0.8,
    density_std: 0.25,
    histogram: {
      edges: [0, 0.5, 1],
      counts: [3, 1],
    },
  },
};

describe('AnalyticsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    analyticsService.getAnalytics.mockResolvedValue(DATA);
  });

  it('carga y muestra el resumen y las secciones', async () => {
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(screen.getByText('Dashboard de análisis')).toBeInTheDocument();
    expect(await screen.findByText('Anotaciones por tipo')).toBeInTheDocument();
    // total de anotaciones en el resumen
    expect(screen.getByText('5')).toBeInTheDocument();
    // % de tejido
    expect(screen.getByText('42.5%')).toBeInTheDocument();
    expect(analyticsService.getAnalytics).toHaveBeenCalledWith(1, {
      spatialBins: 10,
    });
  });

  it('muestra la tabla de distribución de anotaciones', async () => {
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(
      await screen.findByText('Distribución de anotaciones')
    ).toBeInTheDocument();
    expect(screen.getByText('otsu')).toBeInTheDocument();
  });

  it('recarga con nueva resolución espacial al cambiar el filtro', async () => {
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    await screen.findByText('Anotaciones por tipo');
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '20' } });
    await waitFor(() =>
      expect(analyticsService.getAnalytics).toHaveBeenLastCalledWith(1, {
        spatialBins: 20,
      })
    );
  });

  it('muestra un mensaje de error si falla la carga', async () => {
    analyticsService.getAnalytics.mockRejectedValue({
      response: { data: { detail: 'boom' } },
    });
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(await screen.findByText('boom')).toBeInTheDocument();
  });

  it('cierra al pulsar el botón de cerrar', async () => {
    const onClose = vi.fn();
    render(<AnalyticsDashboard imageId={1} onClose={onClose} />);
    await screen.findByText('Anotaciones por tipo');
    fireEvent.click(screen.getByTitle('Cerrar'));
    expect(onClose).toHaveBeenCalled();
  });

  it('muestra el estado vacío de densidad cuando no hay mapa', async () => {
    analyticsService.getAnalytics.mockResolvedValue({
      ...DATA,
      density_zones: null,
    });
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(
      (await screen.findAllByText(/Genera un mapa de densidades/)).length
    ).toBeGreaterThan(0);
  });
});
