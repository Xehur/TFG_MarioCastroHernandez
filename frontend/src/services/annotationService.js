/**
 * Servicio de anotaciones (CRUD) contra el backend.
 */
import apiClient from './api';

export const annotationService = {
  /** Lista las anotaciones de una imagen. Devuelve { total, items }. */
  list: async (imageId, { skip = 0, limit = 500 } = {}) => {
    const response = await apiClient.get(`/images/${imageId}/annotations`, {
      params: { skip, limit },
    });
    return response.data;
  },

  /** Crea una anotación en una imagen. */
  create: async (imageId, payload) => {
    const response = await apiClient.post(`/images/${imageId}/annotations`, payload);
    return response.data;
  },

  /** Actualiza una anotación existente. */
  update: async (annotationId, payload) => {
    const response = await apiClient.put(`/annotations/${annotationId}`, payload);
    return response.data;
  },

  /** Elimina una anotación. */
  remove: async annotationId => {
    const response = await apiClient.delete(`/annotations/${annotationId}`);
    return response.data;
  },

  /** Lista las clases de anotación del usuario. */
  listClasses: async () => {
    const response = await apiClient.get('/annotation-classes');
    return response.data;
  },

  /** Crea una clase de anotación. */
  createClass: async payload => {
    const response = await apiClient.post('/annotation-classes', payload);
    return response.data;
  },

  /** Elimina una clase de anotación. */
  deleteClass: async classId => {
    const response = await apiClient.delete(`/annotation-classes/${classId}`);
    return response.data;
  },
};

export default annotationService;
