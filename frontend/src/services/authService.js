/**
 * Servicio de autenticación.
 * Gestiona el login/registro contra el backend y el almacenamiento
 * del token JWT y del usuario en localStorage.
 */
import apiClient from './api';
import config from '../config/config';

const TOKEN_KEY = config.auth.tokenKey;
const USER_KEY = `${config.auth.tokenKey}_user`;

export const authService = {
  /**
   * Devuelve el token almacenado o null.
   */
  getToken: () => localStorage.getItem(TOKEN_KEY),

  /**
   * Guarda el token de autenticación.
   */
  setToken: token => {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    }
  },

  /**
   * Elimina el token y el usuario almacenados.
   */
  clearToken: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  /**
   * Indica si hay un token guardado.
   */
  isAuthenticated: () => Boolean(localStorage.getItem(TOKEN_KEY)),

  /**
   * Devuelve el usuario cacheado en localStorage (o null).
   */
  getStoredUser: () => {
    const raw = localStorage.getItem(USER_KEY);
    try {
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  /**
   * Persiste el usuario en localStorage.
   */
  setStoredUser: user => {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  },

  /**
   * Registra un nuevo usuario. Devuelve { access_token, user }.
   */
  register: async ({ email, password, fullName }) => {
    const response = await apiClient.post('/auth/register', {
      email,
      password,
      full_name: fullName || null,
    });
    const { access_token, user } = response.data;
    authService.setToken(access_token);
    authService.setStoredUser(user);
    return response.data;
  },

  /**
   * Inicia sesión. Devuelve { access_token, user }.
   */
  login: async ({ email, password }) => {
    const response = await apiClient.post('/auth/login', { email, password });
    const { access_token, user } = response.data;
    authService.setToken(access_token);
    authService.setStoredUser(user);
    return response.data;
  },

  /**
   * Cierra la sesión (limpia token y usuario).
   */
  logout: () => {
    authService.clearToken();
  },

  /**
   * Obtiene el perfil del usuario autenticado desde el backend.
   */
  getCurrentUser: async () => {
    const response = await apiClient.get('/auth/me');
    authService.setStoredUser(response.data);
    return response.data;
  },
};

export default authService;
