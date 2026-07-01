import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { tissueService } from './tissueService';

describe('tissueService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  });

  it('getStats() pide las estadísticas de tejido', async () => {
    apiClient.get.mockResolvedValue({ data: { result_data: { tissue_percent: 12 } } });
    const result = await tissueService.getStats(5);
    expect(apiClient.get).toHaveBeenCalledWith('/images/5/tissue-mask/stats', {
      params: { force: false },
    });
    expect(result.result_data.tissue_percent).toBe(12);
  });

  it('getStats() admite force=true', async () => {
    apiClient.get.mockResolvedValue({ data: {} });
    await tissueService.getStats(5, { force: true });
    expect(apiClient.get).toHaveBeenCalledWith('/images/5/tissue-mask/stats', {
      params: { force: true },
    });
  });

  it('getMaskObjectUrl() descarga el PNG como blob y crea object URL', async () => {
    const blob = new Blob(['x'], { type: 'image/png' });
    apiClient.get.mockResolvedValue({ data: blob });
    const url = await tissueService.getMaskObjectUrl(7);
    expect(apiClient.get).toHaveBeenCalledWith('/images/7/tissue-mask', {
      params: { force: false },
      responseType: 'blob',
    });
    expect(url).toBe('blob:mock-url');
    expect(globalThis.URL.createObjectURL).toHaveBeenCalledWith(blob);
  });

  it('analyze() hace POST para forzar el análisis', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
    const result = await tissueService.analyze(9);
    expect(apiClient.post).toHaveBeenCalledWith('/images/9/analyze/tissue');
    expect(result.id).toBe(1);
  });
});
