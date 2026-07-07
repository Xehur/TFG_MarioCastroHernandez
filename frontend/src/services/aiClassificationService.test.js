import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { aiClassificationService } from './aiClassificationService';

describe('aiClassificationService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:ai');
  });

  it('getStats() pide las estadísticas de la imagen', async () => {
    apiClient.get.mockResolvedValue({ data: { result_data: { rows: 3 } } });
    const result = await aiClassificationService.getStats(5);
    expect(apiClient.get).toHaveBeenCalledWith(
      '/images/5/ai-classification/stats',
      { params: { force: false } }
    );
    expect(result.result_data.rows).toBe(3);
  });

  it('getMapObjectUrl() descarga el PNG como blob', async () => {
    const blob = new Blob(['x'], { type: 'image/png' });
    apiClient.get.mockResolvedValue({ data: blob });
    const url = await aiClassificationService.getMapObjectUrl(7, { force: true });
    expect(apiClient.get).toHaveBeenCalledWith('/images/7/ai-classification', {
      params: { force: true, _ts: expect.any(Number) },
      responseType: 'blob',
    });
    expect(url).toBe('blob:ai');
  });

  it('analyze() hace POST para (re)ejecutar la clasificación', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
    const result = await aiClassificationService.analyze(9);
    expect(apiClient.post).toHaveBeenCalledWith('/images/9/analyze/ai');
    expect(result.id).toBe(1);
  });

  it('getAnnotationStats() pide las estadísticas de la anotación', async () => {
    apiClient.get.mockResolvedValue({ data: { annotation_id: 3 } });
    await aiClassificationService.getAnnotationStats(3);
    expect(apiClient.get).toHaveBeenCalledWith(
      '/annotations/3/ai-classification/stats',
      { params: { force: false } }
    );
  });

  it('analyzeAnnotation() hace POST sobre la anotación', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 2 } });
    await aiClassificationService.analyzeAnnotation(3);
    expect(apiClient.post).toHaveBeenCalledWith('/annotations/3/analyze/ai');
  });
});
