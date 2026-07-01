import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { analysisService } from './analysisService';

describe('analysisService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runAnalysis() hace POST con params y señal de aborto', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1, result_data: {} } });
    const signal = new AbortController().signal;
    const result = await analysisService.runAnalysis(5, {
      gridSize: 128,
      colormap: 'hot',
      signal,
    });
    expect(apiClient.post).toHaveBeenCalledWith('/images/5/analyze', null, {
      params: { grid_size: 128, colormap: 'hot' },
      signal,
    });
    expect(result.id).toBe(1);
  });

  it('runAnalysis() usa valores por defecto', async () => {
    apiClient.post.mockResolvedValue({ data: {} });
    await analysisService.runAnalysis(7);
    expect(apiClient.post).toHaveBeenCalledWith('/images/7/analyze', null, {
      params: { grid_size: 256, colormap: 'viridis' },
      signal: undefined,
    });
  });

  it('getAnalysis() devuelve los datos si existen', async () => {
    apiClient.get.mockResolvedValue({ data: { result_data: { tissue: {} } } });
    const result = await analysisService.getAnalysis(9);
    expect(apiClient.get).toHaveBeenCalledWith('/images/9/analysis');
    expect(result.result_data).toBeTruthy();
  });

  it('getAnalysis() devuelve null en 404', async () => {
    apiClient.get.mockRejectedValue({ response: { status: 404 } });
    const result = await analysisService.getAnalysis(9);
    expect(result).toBeNull();
  });

  it('getAnalysis() relanza otros errores', async () => {
    apiClient.get.mockRejectedValue({ response: { status: 500 } });
    await expect(analysisService.getAnalysis(9)).rejects.toBeTruthy();
  });
});
