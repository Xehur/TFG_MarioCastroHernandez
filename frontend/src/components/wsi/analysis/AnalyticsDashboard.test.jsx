import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../services/analyticsService', () => ({
  analyticsService: {
    getAnalytics: vi.fn(),
  },
}));

vi.mock('../../../services/annotationAnalysisService', () => ({
  annotationAnalysisService: {
    getAnalytics: vi.fn(),
    runAnalysis: vi.fn(),
  },
}));

vi.mock('../../../services/aiClassificationService', () => ({
  aiClassificationService: {
    analyze: vi.fn(),
    analyzeAnnotation: vi.fn(),
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
    XAxis: Stub,
    YAxis: Stub,
    CartesianGrid: Stub,
    Tooltip: Stub,
    Legend: Stub,
  };
});

import { analyticsService } from '../../../services/analyticsService';
import { annotationAnalysisService } from '../../../services/annotationAnalysisService';
import { aiClassificationService } from '../../../services/aiClassificationService';
import AnalyticsDashboard, { formatArea } from './AnalyticsDashboard';

const AI = {
  analyzed_fields: 40,
  tissue_fields: 40,
  dominant_class: 'INVASIVE',
  dominant_name: 'Carcinoma invasivo',
  dominant_percent: 60,
  carcinoma_percent: 70,
  mean_confidence: 0.82,
  field_um: [860, 645],
  disclaimer: 'Uso académico / de investigación.',
  classes: [
    { code: 'INVASIVE', name: 'Carcinoma invasivo', color: [220, 38, 38], percent: 60, area_mm2: 15 },
    { code: 'NORMAL', name: 'Normal', color: [34, 197, 94], percent: 10, area_mm2: 2.5 },
    { code: 'BENIGN', name: 'Benigno', color: [59, 130, 246], percent: 20, area_mm2: 5 },
    { code: 'INSITU', name: 'Carcinoma in situ', color: [245, 158, 11], percent: 10, area_mm2: 2.5 },
  ],
};

const DATA = {
  image_id: 1,
  total_annotations: 5,
  annotated_area_mm2: 1.25,
  by_class: [
    { class: 'Tumor', count: 3, color: '#ff0000', area_mm2: 1 },
    { class: 'Sin clasificar', count: 2, color: '#9ca3af', area_mm2: 0.25 },
  ],
  tissue: {
    tissue_percent: 42.5,
    area_mm2: 25,
    fragments: 2,
    fragment_areas_mm2: [18.75, 6.25],
  },
  density_levels: {
    zones: 3,
    mean_percent: 50,
    levels: [
      { level: 'Baja', range: '< 33 %', count: 1, percent: 33.3 },
      { level: 'Media', range: '33-66 %', count: 1, percent: 33.3 },
      { level: 'Alta', range: '> 66 %', count: 1, percent: 33.3 },
    ],
  },
  image_info: {
    width_px: 40000,
    height_px: 20000,
    mpp: 0.25,
    width_mm: 10,
    height_mm: 5,
    magnification: 40,
  },
  ai: AI,
};

describe('AnalyticsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    analyticsService.getAnalytics.mockResolvedValue(DATA);
  });

  it('muestra el resumen con métricas legibles', async () => {
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(screen.getByText('Dashboard de análisis')).toBeInTheDocument();
    expect(await screen.findByText('25 mm²')).toBeInTheDocument();
    expect(screen.getByText('42,5 % de la imagen')).toBeInTheDocument();
    expect(screen.getByText('Fragmentos')).toBeInTheDocument();
    expect(screen.getByText('70 %')).toBeInTheDocument(); // patrón de carcinoma
    expect(screen.getAllByText('Carcinoma invasivo').length).toBeGreaterThan(0);
    expect(screen.getByText('1,25 mm² anotados')).toBeInTheDocument();
    expect(analyticsService.getAnalytics).toHaveBeenCalledWith(1);
  });

  it('lista las clases IA en orden de gravedad con su superficie', async () => {
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    await screen.findByText('Clasificación de tejido (IA)');
    const rows = screen
      .getAllByRole('row')
      .map(r => r.textContent)
      .filter(t => /Normal|Benigno|in situ|invasivo/.test(t));
    expect(rows[0]).toMatch(/^Normal/);
    expect(rows[3]).toMatch(/^Carcinoma invasivo/);
    expect(screen.getByText('15 mm²')).toBeInTheDocument();
    expect(screen.getByText(/40 de 40 campos con tejido/)).toBeInTheDocument();
    expect(screen.getByText('82 %')).toBeInTheDocument(); // confianza media
  });

  it('muestra información física de la imagen', async () => {
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(await screen.findByText('10 × 5 mm')).toBeInTheDocument();
    expect(screen.getByText('0,25 µm/px')).toBeInTheDocument();
    expect(screen.getByText('40x')).toBeInTheDocument();
  });

  it('ofrece ejecutar la IA si no hay clasificación y recarga al terminar', async () => {
    analyticsService.getAnalytics
      .mockResolvedValueOnce({ ...DATA, ai: null })
      .mockResolvedValueOnce(DATA);
    aiClassificationService.analyze.mockResolvedValue({});
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    fireEvent.click(await screen.findByText('Ejecutar clasificación IA'));
    await waitFor(() => expect(aiClassificationService.analyze).toHaveBeenCalledWith(1));
    expect(await screen.findByText('Re-clasificar')).toBeInTheDocument();
    expect(analyticsService.getAnalytics).toHaveBeenCalledTimes(2);
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
    await screen.findByText('Anotaciones por clase');
    fireEvent.click(screen.getByTitle('Cerrar'));
    expect(onClose).toHaveBeenCalled();
  });

  it('muestra el estado vacío de densidad cuando no hay mapa', async () => {
    analyticsService.getAnalytics.mockResolvedValue({
      ...DATA,
      density_levels: null,
    });
    render(<AnalyticsDashboard imageId={1} onClose={() => {}} />);
    expect(
      await screen.findByText(/Genera un mapa de densidades/)
    ).toBeInTheDocument();
  });

  it('formatea superficies pequeñas y ausentes', () => {
    expect(formatArea(null)).toBe('—');
    expect(formatArea(0.004)).toBe('< 0,01 mm²');
    expect(formatArea(3.456)).toBe('3,46 mm²');
  });
});

describe('AnalyticsDashboard (ámbito anotación)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('usa el servicio de anotación y muestra el título de la región', async () => {
    annotationAnalysisService.getAnalytics.mockResolvedValue({
      ...DATA,
      annotation_id: 42,
      total_annotations: 0,
    });
    render(
      <AnalyticsDashboard imageId={1} annotationId={42} onClose={() => {}} />
    );
    expect(
      await screen.findByText('Dashboard de anotación #42')
    ).toBeInTheDocument();
    expect(annotationAnalysisService.getAnalytics).toHaveBeenCalledWith(42);
    expect(analyticsService.getAnalytics).not.toHaveBeenCalled();
    expect(
      screen.getByText(/tratada como una imagen independiente/)
    ).toBeInTheDocument();
    expect(screen.getByText('Área de la región')).toBeInTheDocument();
    expect(screen.queryByText('Anotaciones por clase')).not.toBeInTheDocument();
  });

  it('lanza el análisis si la región aún no tiene tejido', async () => {
    annotationAnalysisService.getAnalytics
      .mockResolvedValueOnce({ ...DATA, tissue: null, annotation_id: 8 })
      .mockResolvedValueOnce({ ...DATA, annotation_id: 8 });
    annotationAnalysisService.runAnalysis.mockResolvedValue({});
    render(
      <AnalyticsDashboard imageId={1} annotationId={8} onClose={() => {}} />
    );
    await screen.findByText('Densidad del tejido');
    await waitFor(() =>
      expect(annotationAnalysisService.runAnalysis).toHaveBeenCalledWith(8)
    );
    expect(annotationAnalysisService.getAnalytics).toHaveBeenCalledTimes(2);
  });

  it('clasifica la región con la IA de anotación', async () => {
    annotationAnalysisService.getAnalytics.mockResolvedValue({
      ...DATA,
      annotation_id: 5,
      ai: null,
    });
    aiClassificationService.analyzeAnnotation.mockResolvedValue({});
    render(
      <AnalyticsDashboard imageId={1} annotationId={5} onClose={() => {}} />
    );
    fireEvent.click(await screen.findByText('Ejecutar clasificación IA'));
    await waitFor(() =>
      expect(aiClassificationService.analyzeAnnotation).toHaveBeenCalledWith(5)
    );
  });
});
