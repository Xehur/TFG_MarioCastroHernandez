/**
 * Servicio para gestión de imágenes WSI
 */
import apiClient from './api';

export const imageService = {
  /**
   * Obtener lista de imágenes
   */
  getImages: async (skip = 0, limit = 100) => {
    const response = await apiClient.get('/images/', {
      params: { skip, limit },
    });
    return response.data;
  },

  /**
   * Obtener imagen por ID
   */
  getImageById: async imageId => {
    const response = await apiClient.get(`/images/${imageId}`);
    return response.data;
  },

  /**
   * Subir una imagen
   */
  uploadImage: async (file, userId = 1) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);

    const response = await apiClient.post('/images/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  /**
   * Subir múltiples imágenes
   */
  uploadMultipleImages: async (files, userId = 1) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    formData.append('user_id', userId);

    const response = await apiClient.post('/images/upload-multiple', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};
