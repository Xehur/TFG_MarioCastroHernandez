import { createContext } from 'react';

/**
 * Contexto de autenticación.
 * Valores: { user, isAuthenticated, loading, login, register, logout }
 */
export const AuthContext = createContext(null);
