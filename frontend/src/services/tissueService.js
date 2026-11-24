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

  /**
   * Vista previa de la máscara con un factor de umbral (no se guarda).
   * Devuelve { url, tissuePercent } con una object URL del PNG.
   */
  getPreview: async (imageId, thresholdFactor) => {
    const response = await apiClient.get(`/images/${imageId}/tissue-mask/preview`, {
      params: { threshold_factor: thresholdFactor },
      responseType: 'blob',
    });
    const percent = Number(response.headers?.['x-tissue-percent']);
    return {
      url: URL.createObjectURL(response.data),
      tissuePercent: Number.isFinite(percent) ? percent : null,
    };
  },

  /**
   * Fuerza el (re)análisis de tejido. Con `thresholdFactor` aplica y guarda
   * ese factor de umbral para la imagen; sin él conserva el actual.
   */
  analyze: async (imageId, { thresholdFactor } = {}) => {
    const url = `/images/${imageId}/analyze/tissue`;
    const response =
      thresholdFactor != null
        ? await apiClient.post(url, null, { params: { threshold_factor: thresholdFactor } })
        : await apiClient.post(url);
    return response.data;
  },
};

export default tissueService;
