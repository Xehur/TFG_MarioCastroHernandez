import { useState, useEffect, useCallback } from 'react';
import { AuthContext } from './AuthContext';
import { authService } from '../services/authService';

/**
 * Proveedor de autenticación. Mantiene el usuario actual en estado,
 * lo rehidrata al cargar la app y expone login/register/logout.
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [loading, setLoading] = useState(true);

  // Al montar: si hay token, validar la sesión contra el backend
  useEffect(() => {
    let mounted = true;

    const init = async () => {
      if (!authService.isAuthenticated()) {
        if (mounted) setLoading(false);
        return;
      }
      try {
        const current = await authService.getCurrentUser();
        if (mounted) setUser(current);
      } catch {
        // Token inválido/expirado: limpiar sesión
        authService.logout();
        if (mounted) setUser(null);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    init();
    return () => {
      mounted = false;
    };
  }, []);

  const login = useCallback(async credentials => {
    const data = await authService.login(credentials);
    setUser(data.user);
    return data;
  }, []);

  const register = useCallback(async credentials => {
    const data = await authService.register(credentials);
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
  }, []);

  const value = {
    user,
    isAuthenticated: Boolean(user),
    loading,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthProvider;
