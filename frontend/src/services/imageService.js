/**
 * Servicio para gestión de imágenes WSI
 */
import apiClient from './api';
import config from '../config/config';

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
   * Construye la URL del descriptor DZI (metadatos de la pirámide de tiles).
   * La usa OpenSeadragon como tileSource.
   */
  getDziUrl: imageId => `${config.apiBaseUrl}/images/${imageId}/dzi.dzi`,

  /**
   * Construye la URL de un tile concreto (nivel, columna, fila).
   */
  getTileUrl: (imageId, level, col, row) =>
    `${config.apiBaseUrl}/images/${imageId}/dzi_files/${level}/${col}_${row}.jpeg`,

  /**
   * Descarga el descriptor DZI como texto (XML).
   */
  getDzi: async imageId => {
    const response = await apiClient.get(`/images/${imageId}/dzi.dzi`, {
      responseType: 'text',
    });
    return response.data;
  },

  /**
   * Descarga un tile concreto como Blob.
   */
  getTile: async (imageId, level, col, row) => {
    const response = await apiClient.get(
      `/images/${imageId}/dzi_files/${level}/${col}_${row}.jpeg`,
      { responseType: 'blob' }
    );
    return response.data;
  },

  /**
   * Subir una imagen.
   * @param {File} file - archivo a subir
   * @param {Object} options - { userId, onProgress }
   */
  uploadImage: async (file, { userId = 1, onProgress } = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);

    const response = await apiClient.post('/images/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: progressEvent => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
    return response.data;
  },

  /**
   * Subir múltiples imágenes.
   */
  uploadMultipleImages: async (files, { userId = 1, onProgress } = {}) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    formData.append('user_id', userId);

    const response = await apiClient.post('/images/upload-multiple', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: progressEvent => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
    return response.data;
  },
};
