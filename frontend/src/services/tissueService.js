/**
 * Servicio de análisis de imagen (tissue mask) contra el backend.
 */
import apiClient from './api';

export const tissueService = {
  /** Obtiene las estadísticas del análisis de tejido (JSON). */
  getStats: async (imageId, { force = false } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/tissue-mask/stats`, {
      params: { force },
    });
    return response.data;
  },

  /**
   * Descarga el PNG de la máscara de tejido (con auth) y devuelve una object URL
   * lista para usar como fuente de imagen en OpenSeadragon.
   */
  getMaskObjectUrl: async (imageId, { force = false } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/tissue-mask`, {
      params: { force, _ts: Date.now() },
      responseType: 'blob',
    });
    return URL.createObjectURL(response.data);
  },

  /** Fuerza el (re)análisis de tejido. */
  analyze: async imageId => {
    const response = await apiClient.post(`/images/${imageId}/analyze/tissue`);
    return response.data;
  },
};

export default tissueService;
