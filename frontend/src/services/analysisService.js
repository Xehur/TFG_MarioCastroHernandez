/**
 * Servicio de análisis consolidado (tejido + densidad) contra el backend.
 * Sprint 6, issues 37, 41, 42.
 */
import apiClient from './api';

export const analysisService = {
  /**
   * Lanza el análisis completo de una imagen (tejido + densidad).
   * Acepta una señal de aborto opcional para poder cancelar la petición.
   */
  runAnalysis: async (imageId, { gridSize = 256, colormap = 'viridis', signal } = {}) => {
    const response = await apiClient.post(`/images/${imageId}/analyze`, null, {
      params: { grid_size: gridSize, colormap },
      signal,
    });
    return response.data;
  },

  /** Obtiene el último análisis consolidado (o null si no existe). */
  getAnalysis: async imageId => {
    try {
      const response = await apiClient.get(`/images/${imageId}/analysis`);
      return response.data;
    } catch (err) {
      if (err.response?.status === 404) return null;
      throw err;
    }
  },
};

export default analysisService;
