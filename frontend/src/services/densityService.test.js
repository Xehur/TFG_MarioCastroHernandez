import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { densityService } from './densityService';

describe('densityService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  });

  it('getStats() pide la matriz de densidad con parámetros por defecto', async () => {
    apiClient.get.mockResolvedValue({ data: { density_data: { rows: 4 } } });
    const result = await densityService.getStats(5);
    expect(apiClient.get).toHaveBeenCalledWith('/images/5/density-map/stats', {
      params: { grid_size: 256, colormap: 'viridis', force: false },
    });
    expect(result.density_data.rows).toBe(4);
  });

  it('getStats() admite gridSize, colormap y force', async () => {
    apiClient.get.mockResolvedValue({ data: {} });
    await densityService.getStats(5, { gridSize: 128, colormap: 'hot', force: true });
    expect(apiClient.get).toHaveBeenCalledWith('/images/5/density-map/stats', {
      params: { grid_size: 128, colormap: 'hot', force: true },
    });
  });

  it('getMapObjectUrl() descarga el PNG como blob y crea object URL', async () => {
    const blob = new Blob(['x'], { type: 'image/png' });
    apiClient.get.mockResolvedValue({ data: blob });
    const url = await densityService.getMapObjectUrl(7, { gridSize: 512 });
    expect(apiClient.get).toHaveBeenCalledWith('/images/7/density-map', {
      params: { grid_size: 512, colormap: 'viridis', force: false, _ts: expect.any(Number) },
      responseType: 'blob',
    });
    expect(url).toBe('blob:mock-url');
    expect(globalThis.URL.createObjectURL).toHaveBeenCalledWith(blob);
  });

  it('analyze() hace POST con params para forzar la generación', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
    const result = await densityService.analyze(9, { gridSize: 256, colormap: 'jet' });
    expect(apiClient.post).toHaveBeenCalledWith('/images/9/analyze/density', null, {
      params: { grid_size: 256, colormap: 'jet' },
    });
    expect(result.id).toBe(1);
  });
});
