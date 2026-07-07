/**
 * Servicio de clasificación de tejido por IA contra el backend (Sprint 7).
 *
 * Cubre tanto el ámbito de imagen completa (`/images/{id}/ai-classification`)
 * como el de una región anotada (`/annotations/{id}/ai-classification`).
 */
import apiClient from './api';

export const aiClassificationService = {
  /** Estadísticas de la clasificación IA de la imagen (JSON). */
  getStats: async (imageId, { force = false } = {}) => {
    const response = await apiClient.get(
      `/images/${imageId}/ai-classification/stats`,
      { params: { force } }
    );
    return response.data;
  },

  /** Object URL del PNG del mapa de clases IA de la imagen. */
  getMapObjectUrl: async (imageId, { force = false } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/ai-classification`, {
      params: { force, _ts: Date.now() },
      responseType: 'blob',
    });
    return URL.createObjectURL(response.data);
  },

  /** Fuerza la (re)ejecución de la clasificación IA de la imagen. */
  analyze: async imageId => {
    const response = await apiClient.post(`/images/${imageId}/analyze/ai`);
    return response.data;
  },

  /** Estadísticas de la clasificación IA de una región anotada (JSON). */
  getAnnotationStats: async (annotationId, { force = false } = {}) => {
    const response = await apiClient.get(
      `/annotations/${annotationId}/ai-classification/stats`,
      { params: { force } }
    );
    return response.data;
  },

  /** Fuerza la (re)ejecución de la clasificación IA de la región anotada. */
  analyzeAnnotation: async annotationId => {
    const response = await apiClient.post(
      `/annotations/${annotationId}/analyze/ai`
    );
    return response.data;
  },
};

export default aiClassificationService;
