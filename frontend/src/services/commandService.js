/**
 * Servicio de la paleta de comandos contra el backend (Sprint 6, issue 36/40).
 */
import apiClient from './api';

export const commandService = {
  /** Lista los comandos disponibles, con filtro opcional de texto/categoría. */
  getCommands: async ({ q, category } = {}) => {
    const params = {};
    if (q) params.q = q;
    if (category) params.category = category;
    const response = await apiClient.get('/commands', { params });
    return response.data;
  },

  /** Ejecuta un comando de servidor y devuelve su resultado. */
  executeCommand: async (commandId, params = {}) => {
    const response = await apiClient.post('/commands/execute', {
      command_id: commandId,
      params,
    });
    return response.data;
  },
};

export default commandService;
