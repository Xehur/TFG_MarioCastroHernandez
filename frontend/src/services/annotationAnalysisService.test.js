import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { annotationAnalysisService } from './annotationAnalysisService';

describe('annotationAnalysisService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runAnalysis() lanza el análisis con parámetros por defecto', async () => {
    apiClient.post.mockResolvedValue({ data: { annotation_id: 7 } });
    const result = await annotationAnalysisService.runAnalysis(7);
    expect(apiClient.post).toHaveBeenCalledWith(
      '/annotations/7/analyze',
      null,
      { params: { grid_size: 64, colormap: 'viridis' }, signal: undefined }
    );
    expect(result.annotation_id).toBe(7);
  });

  it('runAnalysis() admite gridSize y colormap personalizados', async () => {
    apiClient.post.mockResolvedValue({ data: {} });
    await annotationAnalysisService.runAnalysis(3, {
      gridSize: 128,
      colormap: 'hot',
    });
    expect(apiClient.post).toHaveBeenCalledWith(
      '/annotations/3/analyze',
      null,
      { params: { grid_size: 128, colormap: 'hot' }, signal: undefined }
    );
  });

  it('getAnalytics() pide las analíticas de la anotación', async () => {
    apiClient.get.mockResolvedValue({ data: { annotation_id: 5, tissue: {} } });
    const result = await annotationAnalysisService.getAnalytics(5, {
      spatialBins: 15,
    });
    expect(apiClient.get).toHaveBeenCalledWith('/annotations/5/analytics', {
      params: { spatial_bins: 15 },
    });
    expect(result.annotation_id).toBe(5);
  });

  it('getAnalysis() devuelve null si no existe (404)', async () => {
    apiClient.get.mockRejectedValue({ response: { status: 404 } });
    const result = await annotationAnalysisService.getAnalysis(9);
    expect(result).toBeNull();
  });

  it('getAnalysis() propaga otros errores', async () => {
    apiClient.get.mockRejectedValue({ response: { status: 500 } });
    await expect(annotationAnalysisService.getAnalysis(9)).rejects.toBeTruthy();
  });
});
