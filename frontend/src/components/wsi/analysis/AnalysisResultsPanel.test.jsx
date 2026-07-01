import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../services/analysisService', () => ({
  analysisService: {
    getAnalysis: vi.fn(),
    runAnalysis: vi.fn(),
  },
}));

import { analysisService } from '../../../services/analysisService';
import AnalysisResultsPanel from './AnalysisResultsPanel';

const SUMMARY = {
  tissue: { tissue_percent: 34.2 },
  density: { grid_size: 256, density_mean: 0.42, density_max: 0.9, density_std: 0.25 },
  analyzed_at: '2026-07-01T10:00:00',
};

describe('AnalysisResultsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    analysisService.getAnalysis.mockResolvedValue(null);
    analysisService.runAnalysis.mockResolvedValue({ result_data: SUMMARY });
  });

  it('muestra el estado vacío y el botón Analizar cuando no hay análisis', async () => {
    render(<AnalysisResultsPanel imageId={1} />);
    expect(screen.getByText('Resultados de análisis')).toBeInTheDocument();
    expect(
      await screen.findByText('Analizar imagen')
    ).toBeInTheDocument();
    expect(screen.getByText(/aún no se ha analizado/)).toBeInTheDocument();
  });

  it('carga y muestra un análisis existente', async () => {
    analysisService.getAnalysis.mockResolvedValue({ result_data: SUMMARY });
    render(<AnalysisResultsPanel imageId={2} />);
    expect(await screen.findByText('34.2%')).toBeInTheDocument();
    // densidad máx 0.9 -> 90.0%
    expect(screen.getByText('90.0%')).toBeInTheDocument();
    // variabilidad (std) 0.25 -> 25.0%
    expect(screen.getByText('25.0%')).toBeInTheDocument();
    expect(screen.getByText('256 px')).toBeInTheDocument();
    expect(screen.getByText('Re-analizar')).toBeInTheDocument();
  });

  it('ejecuta el análisis y muestra los resultados', async () => {
    render(<AnalysisResultsPanel imageId={3} />);
    fireEvent.click(await screen.findByText('Analizar imagen'));

    await waitFor(() =>
      expect(analysisService.runAnalysis).toHaveBeenCalledWith(3, {
        gridSize: 256,
        colormap: 'viridis',
        signal: expect.anything(),
      })
    );
    expect(await screen.findByText('34.2%')).toBeInTheDocument();
  });

  it('muestra el progreso y permite cancelar', async () => {
    // runAnalysis nunca resuelve para mantener el estado "running".
    analysisService.runAnalysis.mockReturnValue(new Promise(() => {}));
    render(<AnalysisResultsPanel imageId={4} />);
    fireEvent.click(await screen.findByText('Analizar imagen'));

    expect(await screen.findByText(/Analizando/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Cancelar/));

    expect(await screen.findByText('Analizar imagen')).toBeInTheDocument();
  });

  it('muestra un error si el análisis falla', async () => {
    analysisService.runAnalysis.mockRejectedValue({
      response: { data: { detail: 'fallo análisis' } },
    });
    render(<AnalysisResultsPanel imageId={5} />);
    fireEvent.click(await screen.findByText('Analizar imagen'));
    expect(await screen.findByText('fallo análisis')).toBeInTheDocument();
  });
});
