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
    model: { id: 'x', dataset: 'NCT-CRC-HE-100K' },
    dominant_class: 'TUM',
    dominant_group: 'Tumoral',
    classes: [{ code: 'TUM', name: 'Tumoral', color: [220, 38, 38], percent: 60 }],
    groups: [
      { group: 'Tumoral', color: [220, 38, 38], percent: 60 },
      { group: 'Estroma', color: [245, 158, 11], percent: 40 },
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
    expect(screen.getAllByText(/Tumoral/).length).toBeGreaterThan(0);
    expect(screen.getByText('Ocultar')).toBeInTheDocument();
    expect(screen.getByText('NCT-CRC-HE-100K')).toBeInTheDocument();
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
