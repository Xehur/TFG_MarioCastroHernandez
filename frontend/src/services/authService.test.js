import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { authService } from './authService';

describe('authService', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('setToken / getToken / isAuthenticated', () => {
    expect(authService.isAuthenticated()).toBe(false);
    authService.setToken('abc');
    expect(authService.getToken()).toBe('abc');
    expect(authService.isAuthenticated()).toBe(true);
  });

  it('clearToken elimina token y usuario', () => {
    authService.setToken('abc');
    authService.setStoredUser({ id: 1, email: 'a@b.c' });
    authService.clearToken();
    expect(authService.getToken()).toBeNull();
    expect(authService.getStoredUser()).toBeNull();
  });

  it('getStoredUser devuelve null si el JSON es inválido', () => {
    localStorage.setItem('wsi_auth_token_user', '{not-json');
    expect(authService.getStoredUser()).toBeNull();
  });

  it('register guarda token y usuario', async () => {
    apiClient.post.mockResolvedValue({
      data: { access_token: 'tok', user: { id: 1, email: 'a@b.c' } },
    });
    const result = await authService.register({
      email: 'a@b.c',
      password: '123456',
      fullName: 'Ana',
    });
    expect(apiClient.post).toHaveBeenCalledWith('/auth/register', {
      email: 'a@b.c',
      password: '123456',
      full_name: 'Ana',
    });
    expect(authService.getToken()).toBe('tok');
    expect(result.user.email).toBe('a@b.c');
  });

  it('login guarda token y usuario', async () => {
    apiClient.post.mockResolvedValue({
      data: { access_token: 'tok2', user: { id: 2, email: 'x@y.z' } },
    });
    await authService.login({ email: 'x@y.z', password: 'pw' });
    expect(authService.getToken()).toBe('tok2');
    expect(authService.getStoredUser().id).toBe(2);
  });

  it('logout limpia la sesión', () => {
    authService.setToken('abc');
    authService.logout();
    expect(authService.getToken()).toBeNull();
  });

  it('getCurrentUser pide /auth/me y cachea el usuario', async () => {
    apiClient.get.mockResolvedValue({ data: { id: 3, email: 'm@e.c' } });
    const user = await authService.getCurrentUser();
    expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    expect(user.id).toBe(3);
    expect(authService.getStoredUser().id).toBe(3);
  });
});
