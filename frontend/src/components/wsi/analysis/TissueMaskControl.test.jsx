import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { createRef } from 'react';

vi.mock('../../../services/tissueService', () => ({
  tissueService: {
    getStats: vi.fn(),
    getMaskObjectUrl: vi.fn(),
    getPreview: vi.fn(),
    analyze: vi.fn(),
  },
}));

import { tissueService } from '../../../services/tissueService';
import TissueMaskControl from './TissueMaskControl';

function makeViewer() {
  const item = { setOpacity: vi.fn() };
  return {
    item,
    addSimpleImage: vi.fn(opts => opts.success({ item })),
    world: { removeItem: vi.fn() },
  };
}

describe('TissueMaskControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mask');
    globalThis.URL.revokeObjectURL = vi.fn();
    tissueService.getStats.mockResolvedValue({
      result_data: { tissue_percent: 23.4 },
    });
    tissueService.getMaskObjectUrl.mockResolvedValue('blob:mask');
  });

  it('renderiza la cabecera y el botón de mostrar', () => {
    render(<TissueMaskControl viewer={makeViewer()} imageId={1} />);
    expect(screen.getByText('Máscara de tejido')).toBeInTheDocument();
    expect(screen.getByText('Mostrar')).toBeInTheDocument();
  });

  it('deshabilita el toggle si no hay viewer', () => {
    render(<TissueMaskControl viewer={null} imageId={1} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('muestra la máscara y las estadísticas al activar', async () => {
    const viewer = makeViewer();
    render(<TissueMaskControl viewer={viewer} imageId={1} />);

    fireEvent.click(screen.getByText('Mostrar'));

    await waitFor(() =>
      expect(tissueService.getMaskObjectUrl).toHaveBeenCalledWith(1)
    );
    expect(viewer.addSimpleImage).toHaveBeenCalled();
    expect(await screen.findByText('23.4%')).toBeInTheDocument();
    expect(screen.getByText('Ocultar')).toBeInTheDocument();
    expect(screen.getByLabelText('Opacidad')).toBeInTheDocument();
  });

  it('ajusta la opacidad del overlay', async () => {
    const viewer = makeViewer();
    render(<TissueMaskControl viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('23.4%');

    const slider = screen.getByLabelText('Opacidad');
    fireEvent.change(slider, { target: { value: '0.8' } });
    expect(viewer.item.setOpacity).toHaveBeenCalledWith(0.8);
  });

  it('oculta la máscara al desactivar', async () => {
    const viewer = makeViewer();
    render(<TissueMaskControl viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('Ocultar');

    fireEvent.click(screen.getByText('Ocultar'));
    expect(viewer.world.removeItem).toHaveBeenCalledWith(viewer.item);
  });

  it('muestra un error si falla la carga', async () => {
    tissueService.getMaskObjectUrl.mockRejectedValue({
      response: { data: { detail: 'fallo backend' } },
    });
    render(<TissueMaskControl viewer={makeViewer()} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    expect(await screen.findByText('fallo backend')).toBeInTheDocument();
  });

  it('re-analiza al pulsar Re-analizar', async () => {
    const viewer = makeViewer();
    tissueService.analyze.mockResolvedValue({ id: 2 });
    render(<TissueMaskControl viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('23.4%');

    fireEvent.click(screen.getByText(/Re-analizar/));
    await waitFor(() => expect(tissueService.analyze).toHaveBeenCalledWith(1));
  });

  it('el deslizador de umbral muestra una vista previa sin guardarla', async () => {
    tissueService.getPreview.mockResolvedValue({ url: 'blob:preview', tissuePercent: 15.2 });
    const viewer = makeViewer();
    render(<TissueMaskControl viewer={viewer} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('23.4%');
    expect(screen.getByText(/automático/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Umbral de detección/), {
      target: { value: '2' },
    });
    await waitFor(() => expect(tissueService.getPreview).toHaveBeenCalledWith(1, 2));
    expect(await screen.findByText('15.2%')).toBeInTheDocument();
    expect(screen.getByText(/sin guardar/)).toBeInTheDocument();
    // La vista previa sustituye al overlay, pero no se ha guardado nada.
    expect(viewer.addSimpleImage).toHaveBeenLastCalledWith(
      expect.objectContaining({ url: 'blob:preview' })
    );
    expect(tissueService.analyze).not.toHaveBeenCalled();
  });

  it('Aplicar guarda el umbral elegido para la imagen', async () => {
    tissueService.getPreview.mockResolvedValue({ url: 'blob:preview', tissuePercent: 15.2 });
    tissueService.analyze.mockResolvedValue({ id: 3 });
    render(<TissueMaskControl viewer={makeViewer()} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('23.4%');

    fireEvent.change(screen.getByLabelText(/Umbral de detección/), {
      target: { value: '1.5' },
    });
    await screen.findByText('15.2%');
    tissueService.getStats.mockResolvedValue({
      result_data: { tissue_percent: 15.0, threshold_factor: 1.5 },
    });
    fireEvent.click(screen.getByText('Aplicar'));

    await waitFor(() =>
      expect(tissueService.analyze).toHaveBeenCalledWith(1, { thresholdFactor: 1.5 })
    );
    expect(await screen.findByText('15.0%')).toBeInTheDocument();
    expect(screen.queryByText(/sin guardar/)).not.toBeInTheDocument();
    expect(screen.getByText('Volver al umbral automático')).toBeInTheDocument();
  });

  it('Descartar vuelve a la máscara guardada', async () => {
    tissueService.getPreview.mockResolvedValue({ url: 'blob:preview', tissuePercent: 15.2 });
    render(<TissueMaskControl viewer={makeViewer()} imageId={1} />);
    fireEvent.click(screen.getByText('Mostrar'));
    await screen.findByText('23.4%');

    fireEvent.change(screen.getByLabelText(/Umbral de detección/), {
      target: { value: '2' },
    });
    await screen.findByText('15.2%');
    fireEvent.click(screen.getByText('Descartar'));

    await waitFor(() => expect(screen.queryByText(/sin guardar/)).not.toBeInTheDocument());
    expect(screen.getByText(/automático/)).toBeInTheDocument();
    expect(tissueService.analyze).not.toHaveBeenCalled();
  });

  it('muestra la máscara al invocar show() desde la ref (paleta de comandos)', async () => {
    const viewer = makeViewer();
    const ref = createRef();
    render(<TissueMaskControl ref={ref} viewer={viewer} imageId={1} />);

    await act(async () => {
      ref.current.show();
    });

    await waitFor(() =>
      expect(tissueService.getMaskObjectUrl).toHaveBeenCalledWith(1)
    );
    expect(viewer.addSimpleImage).toHaveBeenCalled();
    expect(await screen.findByText('Ocultar')).toBeInTheDocument();
  });

  it('alterna la máscara al invocar toggle() desde la ref', async () => {
    const viewer = makeViewer();
    const ref = createRef();
    render(<TissueMaskControl ref={ref} viewer={viewer} imageId={1} />);

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
