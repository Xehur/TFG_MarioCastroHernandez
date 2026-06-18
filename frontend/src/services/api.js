/**
 * Servicio base para peticiones HTTP usando Axios.
 * Incluye interceptores de autenticación y manejo de errores estructurado.
 */
import axios from 'axios';
import config from '../config/config';
import { authService } from './authService';
import { normalizeApiError } from '../utils/apiError';

const apiClient = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: inyecta el token de autenticación si existe
apiClient.interceptors.request.use(
  requestConfig => {
    const token = authService.getToken();
    if (token) {
      requestConfig.headers.Authorization = `Bearer ${token}`;
    }
    return requestConfig;
  },
  error => Promise.reject(normalizeApiError(error))
);

// Response interceptor: normaliza errores y gestiona el 401
apiClient.interceptors.response.use(
  response => response,
  error => {
    const apiError = normalizeApiError(error);

    if (apiError.status === 401) {
      // Token inválido o expirado: limpiamos la sesión
      authService.clearToken();
    }

    if (config.isDevelopment) {
      console.error(`[API] ${apiError.status || apiError.code}: ${apiError.message}`);
    }

    return Promise.reject(apiError);
  }
);

export default apiClient;
