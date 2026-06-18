/**
 * Servicio de autenticación.
 * Gestiona el almacenamiento del token de auth en localStorage.
 * Preparado para integrarse con el backend cuando exista login.
 */
import config from '../config/config';

const TOKEN_KEY = config.auth.tokenKey;

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
   * Elimina el token almacenado.
   */
  clearToken: () => localStorage.removeItem(TOKEN_KEY),

  /**
   * Indica si hay un token guardado.
   */
  isAuthenticated: () => Boolean(localStorage.getItem(TOKEN_KEY)),
};

export default authService;
