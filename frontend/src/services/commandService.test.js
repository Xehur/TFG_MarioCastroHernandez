import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from './api';
import { commandService } from './commandService';

describe('commandService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCommands() sin filtros pide la lista completa', async () => {
    apiClient.get.mockResolvedValue({ data: { commands: [], total: 0 } });
    await commandService.getCommands();
    expect(apiClient.get).toHaveBeenCalledWith('/commands', { params: {} });
  });

  it('getCommands() incluye q y category cuando se pasan', async () => {
    apiClient.get.mockResolvedValue({ data: { commands: [] } });
    await commandService.getCommands({ q: 'densidad', category: 'Análisis' });
    expect(apiClient.get).toHaveBeenCalledWith('/commands', {
      params: { q: 'densidad', category: 'Análisis' },
    });
  });

  it('executeCommand() hace POST con command_id y params', async () => {
    apiClient.post.mockResolvedValue({ data: { status: 'success' } });
    const result = await commandService.executeCommand('run-full-analysis', {
      image_id: 5,
    });
    expect(apiClient.post).toHaveBeenCalledWith('/commands/execute', {
      command_id: 'run-full-analysis',
      params: { image_id: 5 },
    });
    expect(result.status).toBe('success');
  });

  it('executeCommand() usa params vacío por defecto', async () => {
    apiClient.post.mockResolvedValue({ data: {} });
    await commandService.executeCommand('go-gallery');
    expect(apiClient.post).toHaveBeenCalledWith('/commands/execute', {
      command_id: 'go-gallery',
      params: {},
    });
  });
});
