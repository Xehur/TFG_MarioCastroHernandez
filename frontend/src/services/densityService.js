/**
 * Servicio del mapa de densidades contra el backend (Sprint 6, issue 39).
 */
import apiClient from './api';

export const densityService = {
  /** Obtiene la matriz de densidades y metadatos (JSON). */
  getStats: async (imageId, { gridSize = 256, colormap = 'viridis', force = false } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/density-map/stats`, {
      params: { grid_size: gridSize, colormap, force },
    });
    return response.data;
  },

  /**
   * Descarga el PNG del heatmap de densidad (con auth) y devuelve una object URL
   * lista para usar como fuente de imagen en OpenSeadragon.
   */
  getMapObjectUrl: async (imageId, { gridSize = 256, colormap = 'viridis', force = false } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/density-map`, {
      params: { grid_size: gridSize, colormap, force, _ts: Date.now() },
      responseType: 'blob',
    });
    return URL.createObjectURL(response.data);
  },

  /** Fuerza la (re)generación del mapa de densidades. */
  analyze: async (imageId, { gridSize = 256, colormap = 'viridis' } = {}) => {
    const response = await apiClient.post(`/images/${imageId}/analyze/density`, null, {
      params: { grid_size: gridSize, colormap },
    });
    return response.data;
  },
};

export default densityService;
