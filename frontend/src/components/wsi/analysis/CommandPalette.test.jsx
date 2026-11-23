import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

vi.mock('../../../services/commandService', () => ({
  commandService: {
    getCommands: vi.fn(),
    executeCommand: vi.fn(),
  },
}));

import { commandService } from '../../../services/commandService';
import CommandPalette from './CommandPalette';

const COMMANDS = [
  {
    id: 'run-full-analysis',
    name: 'Analizar imagen (completo)',
    description: 'Ejecuta la detección de tejido y densidad.',
    category: 'Análisis',
    icon: 'Activity',
    target: 'backend',
    action: null,
    route: null,
    params: [{ name: 'image_id', type: 'int', required: true }],
    keywords: ['analisis', 'densidad'],
  },
  {
    id: 'open-analytics-dashboard',
    name: 'Abrir dashboard de análisis',
    description: 'Muestra gráficas y tablas.',
    category: 'Visualización',
    icon: 'BarChart3',
    target: 'frontend',
    action: 'open-analytics',
    route: null,
    params: [],
    keywords: ['graficas'],
  },
  {
    id: 'go-gallery',
    name: 'Ir a la galería',
    description: 'Navega al listado.',
    category: 'Navegación',
    icon: 'Images',
    target: 'frontend',
    action: 'navigate',
    route: '/',
    params: [],
    keywords: ['galeria'],
  },
];

const openPalette = () => {
  act(() => {
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })
    );
  });
};

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    commandService.getCommands.mockResolvedValue({ commands: COMMANDS });
    commandService.executeCommand.mockResolvedValue({ status: 'success' });
  });

  it('no muestra nada hasta que se pulsa Ctrl+K', () => {
    render(<CommandPalette context={{ imageId: 1 }} onCommand={() => {}} />);
    expect(screen.queryByPlaceholderText('Buscar comando…')).toBeNull();
  });

  it('se abre con Ctrl+K y lista los comandos agrupados', async () => {
    render(<CommandPalette context={{ imageId: 1 }} onCommand={() => {}} />);
    openPalette();
    expect(
      await screen.findByText('Analizar imagen (completo)')
    ).toBeInTheDocument();
    expect(screen.getByText('Análisis')).toBeInTheDocument();
    expect(screen.getByText('Navegación')).toBeInTheDocument();
  });

  it('filtra en tiempo real por texto', async () => {
    render(<CommandPalette context={{ imageId: 1 }} onCommand={() => {}} />);
    openPalette();
    await screen.findByText('Analizar imagen (completo)');
    fireEvent.change(screen.getByPlaceholderText('Buscar comando…'), {
      target: { value: 'galeria' },
    });
    expect(screen.getByText('Ir a la galería')).toBeInTheDocument();
    expect(screen.queryByText('Analizar imagen (completo)')).toBeNull();
  });

  it('ejecuta un comando de servidor con el image_id del contexto', async () => {
    render(<CommandPalette context={{ imageId: 7 }} onCommand={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByText('Analizar imagen (completo)'));
    await waitFor(() =>
      expect(commandService.executeCommand).toHaveBeenCalledWith(
        'run-full-analysis',
        { image_id: 7 }
      )
    );
  });

  it('delega los comandos de frontend en onCommand', async () => {
    const onCommand = vi.fn();
    render(<CommandPalette context={{ imageId: 1 }} onCommand={onCommand} />);
    openPalette();
    fireEvent.click(await screen.findByText('Ir a la galería'));
    expect(onCommand).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'go-gallery', action: 'navigate' })
    );
  });

  it('muestra mensaje de error si la ejecución falla', async () => {
    commandService.executeCommand.mockRejectedValue({
      response: { data: { detail: 'fallo' } },
    });
    render(<CommandPalette context={{ imageId: 7 }} onCommand={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByText('Analizar imagen (completo)'));
    expect(await screen.findByText('fallo')).toBeInTheDocument();
  });

  it('se cierra con Escape', async () => {
    render(<CommandPalette context={{ imageId: 1 }} onCommand={() => {}} />);
    openPalette();
    const input = await screen.findByPlaceholderText('Buscar comando…');
    fireEvent.keyDown(input, { key: 'Escape' });
    await waitFor(() =>
      expect(screen.queryByPlaceholderText('Buscar comando…')).toBeNull()
    );
  });

  it('navega con las flechas y ejecuta con Enter', async () => {
    const onCommand = vi.fn();
    render(<CommandPalette context={{ imageId: 1 }} onCommand={onCommand} />);
    openPalette();
    const input = await screen.findByPlaceholderText('Buscar comando…');
    // Baja hasta el tercer comando (go-gallery) y ejecuta.
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommand).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'go-gallery' })
    );
  });

  it('muestra estado vacío cuando no hay coincidencias', async () => {
    render(<CommandPalette context={{ imageId: 1 }} onCommand={() => {}} />);
    openPalette();
    await screen.findByText('Analizar imagen (completo)');
    fireEvent.change(screen.getByPlaceholderText('Buscar comando…'), {
      target: { value: 'zzznomatch' },
    });
    expect(screen.getByText('No hay comandos que coincidan.')).toBeInTheDocument();
  });
});
