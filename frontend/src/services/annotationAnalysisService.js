/**
 * Servicio de análisis de zonas anotadas (anotaciones tratadas como WSI aparte).
 *
 * Ejecuta y recupera los análisis (tejido, densidad, consolidado y analíticas)
 * acotados a la región de una anotación, contra los endpoints
 * ``/annotations/:id/...`` del backend.
 */
import apiClient from './api';

export const annotationAnalysisService = {
  /**
   * Lanza el análisis completo (tejido + densidad) de la región de la
   * anotación. Devuelve el resumen consolidado.
   */
  runAnalysis: async (
    annotationId,
    { gridSize = 64, colormap = 'viridis', signal } = {}
  ) => {
    const response = await apiClient.post(
      `/annotations/${annotationId}/analyze`,
      null,
      { params: { grid_size: gridSize, colormap }, signal }
    );
    return response.data;
  },

  /** Obtiene el último análisis consolidado de la anotación (o null). */
  getAnalysis: async annotationId => {
    try {
      const response = await apiClient.get(
        `/annotations/${annotationId}/analysis`
      );
      return response.data;
    } catch (err) {
      if (err.response?.status === 404) return null;
      throw err;
    }
  },

  /** Obtiene las analíticas (tejido + densidad por zonas) de la anotación. */
  getAnalytics: async (annotationId, { spatialBins = 10 } = {}) => {
    const response = await apiClient.get(
      `/annotations/${annotationId}/analytics`,
      { params: { spatial_bins: spatialBins } }
    );
    return response.data;
  },
};

export default annotationAnalysisService;
