/**
 * Servicio de analíticas contra el backend (Sprint 6, issue 49).
 *
 * Recupera el conjunto de datos listos para gráficas y tablas generado por el
 * endpoint GET /images/:id/analytics.
 */
import apiClient from './api';

export const analyticsService = {
  /**
   * Obtiene los datos de analíticas de una imagen.
   * @param {number} imageId
   * @param {{ spatialBins?: number }} [opts]
   */
  getAnalytics: async (imageId, { spatialBins = 10 } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/analytics`, {
      params: { spatial_bins: spatialBins },
    });
    return response.data;
  },
};

export default analyticsService;
