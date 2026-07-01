import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
  },
}));

import apiClient from './api';
import { analyticsService } from './analyticsService';

describe('analyticsService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getAnalytics() pide los datos con spatial_bins por defecto', async () => {
    apiClient.get.mockResolvedValue({ data: { total_annotations: 3 } });
    const result = await analyticsService.getAnalytics(5);
    expect(apiClient.get).toHaveBeenCalledWith('/images/5/analytics', {
      params: { spatial_bins: 10 },
    });
    expect(result.total_annotations).toBe(3);
  });

  it('getAnalytics() admite spatialBins personalizado', async () => {
    apiClient.get.mockResolvedValue({ data: {} });
    await analyticsService.getAnalytics(9, { spatialBins: 20 });
    expect(apiClient.get).toHaveBeenCalledWith('/images/9/analytics', {
      params: { spatial_bins: 20 },
    });
  });
});
