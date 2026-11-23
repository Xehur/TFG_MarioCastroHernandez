import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { createRef } from 'react';

vi.mock('../../../services/aiClassificationService', () => ({
  aiClassificationService: {
    getStats: vi.fn(),
    getMapObjectUrl: vi.fn(),
    analyze: vi.fn(),
  },
}));

import { aiClassificationService } from '../../../services/aiClassificationService';
import AIClassificationControl from './AIClassificationControl';

function makeViewer() {
  const item = { setOpacity: vi.fn() };
  return {
    item,
    addSimpleImage: vi.fn(opts => opts.success({ item })),
    world: { removeItem: vi.fn() },
  };
}

const SAMPLE = {
  result_data: {
    model: {
      id: 'inceptionv3-bach-he',
      dataset: 'BACH (ICIAR 2018) Photos',
      device: 'cuda',
      gpu_name: 'AMD Radeon RX 7800 XT',
    },
    dominant_class: 'INVASIVE',
    dominant_group: 'Carcinoma invasivo',
    tissue_patches: 12,
    total_patches: 20,
    sampling: { field_um: [860, 645], sampled: false, tissue_cells: 12 },
    disclaimer: 'Uso académico / de investigación.',
    classes: [
      {
        code: 'INVASIVE',
        name: 'Carcinoma invasivo',
        color: [220, 38, 38],
        percent: 75,
      },
      { code: 'NORMAL', name: 'Normal', color: [34, 197, 94], percent: 25 },
    ],
    groups: [
      { group: 'Normal', color: [34, 197, 94], percent: 25 },
      { group: 'Benigno', color: [59, 130, 246], percent: 0 },
      { group: 'Carcinoma in situ', color: [245, 158, 11], percent: 0 },
      { group: 'Carcinoma invasivo', color: [220, 38, 38], percent: 75 },
    ],
  },
};

describe('AIClassificationControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:ai');
    globalThis.URL.revokeObjectURL = vi.fn();
    aiClassificationService.getStats.mockResolvedValue(SAMPLE);
    aiClassificationService.getMapObjectUrl.mockResolvedValue('blob:ai');
  });

  it('renderiza la cabecera y el botón de mostrar', () => {
    render(<AIClassificationControl viewer={makeViewer()} imageId={1} />);
    expect(screen.getByText('Clasificación IA')).toBeInTheDocument();
    expect(screen.getByText('Mostrar')).toBeInTheDocument();
  });

  it('deshabilita el toggle si no hay viewer', () => {
    render(<AIClassificationControl viewer={null} imageId={1} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('muestra el overlay y la distribución al activar', async () => {
    const viewer = makeViewer();
    render(<AIClassificationControl viewer={viewer} imageId={1} />);

    fireEvent.click(screen.getByText('Mostrar'));

    await waitFor(() =>
      expect(aiClassificationService.getMapObjectUrl).toHaveBeenCalledWith(1, {
        force: false,
      })
    );
    expect(viewer.addSimpleImage).toHaveBeenCalled();
    expect(await screen.findByText('Predominante')).toBeInTheDocument();
    expect(screen.getAllByText(/Carcinoma invasivo/).length).toBeGreaterThan(0);
    // Solo se listan las clases con presencia (Benigno e In situ a 0 %).
    expect(screen.queryByText('Benigno')).not.toBeInTheDocument();
    expect(screen.getByText('Ocultar')).toBeInTheDocument();
    expect(screen.getByText('BACH (ICIAR 2018) Photos')).toBeInTheDocument();
    expect(screen.getByText('GPU')).toBeInTheDocument();
    expect(
      screen.getByText(/12 de 12 campos con tejido analizados · campo ≈ 860×645 µm/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Uso académico/)).toBeInTheDocument();
  });

  it('show() imperativo fuerza el overlay', async () => {
    const ref = createRef();
    const viewer = makeViewer();
    render(<AIClassificationControl ref={ref} viewer={viewer} imageId={2} />);

    ref.current.show();

    await waitFor(() =>
      expect(aiClassificationService.getStats).toHaveBeenCalledWith(2, {
        force: false,
      })
    );
    expect(viewer.addSimpleImage).toHaveBeenCalled();
  });
});
