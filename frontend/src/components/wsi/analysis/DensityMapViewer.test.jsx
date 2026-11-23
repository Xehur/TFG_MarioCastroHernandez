import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { createRef } from 'react';

vi.mock('../../../services/densityService', () => ({
  densityService: {
    getStats: vi.fn(),
    getMapObjectUrl: vi.fn(),
    analyze: vi.fn(),
  },
}));

let moveHandler = null;
vi.mock('openseadragon', () => ({
  default: {
    MouseTracker: class {
      constructor(opts) {
        moveHandler = opts.moveHandler;
        this.destroy = vi.fn();
      }
    },
  },
}));

import { densityService } from '../../../services/densityService';
import DensityMapViewer from './DensityMapViewer';

function makeViewer() {
  const item = { setOpacity: vi.fn() };
  return {
    item,
    canvas: document.createElement('div'),
    addSimpleImage: vi.fn(opts => opts.success({ item })),
    world: { removeItem: vi.fn() },
    viewport: {
      pointFromPixel: p => p,
      viewportToImageCoordinates: p => ({ x: p.x, y: p.y }),
    },
  };
}

const DENSITY_DATA = {
  rows: 2,
  cols: 2,
  grid_size: 100,
  density_min: 0,
  density_max: 1,
  density_mean: 0.5,
  matrix: [
    [0, 0.5],
    [1, 0.25],
  ],
  colorbar: [
    [68, 1, 84],
    [253, 231, 37],
  ],
};

describe('DensityMapViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    moveHandler = null;
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:density');
    globalThis.URL.revokeObjectURL = vi.fn();
    densityService.getStats.mockResolvedValue({ density_data: DENSITY_DATA });
    densityService.getMapObjectUrl.mockResolvedValue('blob:density');
  });

  it('renderiza la cabecera, selectores y botón mostrar', () => {
    render(<DensityMapViewer viewer={makeViewer()} imageId={1} />);
    expect(screen.getByText('Mapa de densidad')).toBeInTheDocument();
    expect(screen.getByText('Mostrar')).toBeInTheDocument();
    expect(screen.getByText('Grid')).toBeInTheDocument();
    expect(screen.getByText('Color')).toBeInTheDocument();
  });

  it('deshabilita el toggle si no hay viewer', () => {
    render(<DensityMapViewer viewer={null} imageId={1} />);
    expect(screen.getByRole('button', { name: /Mostrar/ })).toBeDisabled();
  });

  it('muestra el heatmap, la leyenda y estadísticas al activar', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={1} />);

    fireEvent.click(screen.getByText('Mostrar'));

    await waitFor(() =>
      expect(densityService.getMapObjectUrl).toHaveBeenCalled()
    );
    expect(viewer.addSimpleImage).toHaveBeenCalled();
    // Media = 0.5 -> 50.0%
    expect(await screen.findByText('50.0%')).toBeInTheDocument();
    expect(screen.getByText('Ocultar')).toBeInTheDocument();
    expect(screen.getByLabelText('Opacidad')).toBeInTheDocument();
    expect(screen.getByText('densidad')).toBeInTheDocument();
  });

  it('pasa el grid_size seleccionado al servicio', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={3} />);

    fireEvent.change(screen.getByDisplayValue('256 px'), {
      target: { value: '512' },
    });
    fireEvent.click(screen.getByText('Mostrar'));

    await waitFor(() =>
      expect(densityService.getStats).toHaveBeenCalledWith(3, {
        gridSize: 512,
        colormap: 'viridis',
        force: false,
      })
    );
  });

  it('ajusta la opacidad del overlay', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('50.0%');

    fireEvent.change(screen.getByLabelText('Opacidad'), {
      target: { value: '0.9' },
    });
    expect(viewer.item.setOpacity).toHaveBeenCalledWith(0.9);
  });

  it('muestra el tooltip de densidad al mover el ratón', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('50.0%');

    expect(moveHandler).toBeTypeOf('function');
    // Punto en (150, 0) -> col=1, row=0 -> densidad 0.5
    act(() => {
      moveHandler({
        position: { x: 150, y: 0 },
        originalEvent: { clientX: 20, clientY: 30 },
      });
    });

    expect(await screen.findByText('Densidad: 50.0%')).toBeInTheDocument();
  });

  it('recarga con el colormap seleccionado al cambiarlo con el mapa activo', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={4} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('50.0%');

    densityService.getMapObjectUrl.mockClear();
    fireEvent.change(screen.getByDisplayValue('viridis'), {
      target: { value: 'hot' },
    });

    await waitFor(() =>
      expect(densityService.getMapObjectUrl).toHaveBeenCalledWith(4, {
        gridSize: 256,
        colormap: 'hot',
        force: false,
      })
    );
  });

  it('oculta el heatmap al desactivar', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('Ocultar');

    fireEvent.click(screen.getByText('Ocultar'));
    expect(viewer.world.removeItem).toHaveBeenCalledWith(viewer.item);
  });

  it('muestra un error si falla la carga', async () => {
    densityService.getMapObjectUrl.mockRejectedValue({
      response: { data: { detail: 'fallo densidad' } },
    });
    render(<DensityMapViewer viewer={makeViewer()} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    expect(await screen.findByText('fallo densidad')).toBeInTheDocument();
  });

  it('re-genera al pulsar Re-generar', async () => {
    const viewer = makeViewer();
    render(<DensityMapViewer viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('50.0%');

    fireEvent.click(screen.getByText(/Re-generar/));
    await waitFor(() =>
      expect(densityService.getStats).toHaveBeenLastCalledWith(1, {
        gridSize: 256,
        colormap: 'viridis',
        force: true,
      })
    );
  });

  it('muestra el mapa al invocar show() desde la ref (paleta de comandos)', async () => {
    const viewer = makeViewer();
    const ref = createRef();
    render(<DensityMapViewer ref={ref} viewer={viewer} imageId={1} />);

    await act(async () => {
      ref.current.show();
    });

    await waitFor(() =>
      expect(densityService.getMapObjectUrl).toHaveBeenCalled()
    );
    expect(viewer.addSimpleImage).toHaveBeenCalled();
    expect(await screen.findByText('Ocultar')).toBeInTheDocument();
  });

  it('alterna el mapa al invocar toggle() desde la ref', async () => {
    const viewer = makeViewer();
    const ref = createRef();
    render(<DensityMapViewer ref={ref} viewer={viewer} imageId={1} />);

    await act(async () => {
      ref.current.toggle();
    });
    expect(await screen.findByText('Ocultar')).toBeInTheDocument();
    expect(viewer.addSimpleImage).toHaveBeenCalled();

    await act(async () => {
      ref.current.toggle();
    });
    expect(await screen.findByText('Mostrar')).toBeInTheDocument();
    expect(viewer.world.removeItem).toHaveBeenCalledWith(viewer.item);
  });
});
