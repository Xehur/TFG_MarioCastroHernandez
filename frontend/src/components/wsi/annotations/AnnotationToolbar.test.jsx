import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AnnotationToolbar from './AnnotationToolbar';

const baseGrid = { enabled: false, size: 256, opacity: 0.4 };

const setup = (overrides = {}) => {
  const props = {
    tool: 'select',
    onToolChange: vi.fn(),
    color: '#FF0000',
    onColorChange: vi.fn(),
    grid: baseGrid,
    onGridChange: vi.fn(),
    ...overrides,
  };
  render(<AnnotationToolbar {...props} />);
  return props;
};

describe('AnnotationToolbar', () => {
  it('renderiza las cuatro herramientas', () => {
    setup();
    expect(screen.getByTitle('Seleccionar')).toBeInTheDocument();
    expect(screen.getByTitle('Rectángulo')).toBeInTheDocument();
    expect(screen.getByTitle('Círculo')).toBeInTheDocument();
    expect(screen.getByTitle('Polígono')).toBeInTheDocument();
  });

  it('cambia de herramienta al pulsar', () => {
    const props = setup();
    fireEvent.click(screen.getByTitle('Rectángulo'));
    expect(props.onToolChange).toHaveBeenCalledWith('rectangle');
  });

  it('cambia el color con un swatch', () => {
    const props = setup();
    fireEvent.click(screen.getByTitle('#00C853'));
    expect(props.onColorChange).toHaveBeenCalledWith('#00C853');
  });

  it('activa el grid', () => {
    const props = setup();
    fireEvent.click(screen.getByLabelText('Grid'));
    expect(props.onGridChange).toHaveBeenCalledWith({ ...baseGrid, enabled: true });
  });

  it('muestra los controles del grid cuando está activo', () => {
    setup({ grid: { ...baseGrid, enabled: true } });
    expect(screen.getByText(/Celda/i)).toBeInTheDocument();
    expect(screen.getByText(/Opacidad/i)).toBeInTheDocument();
  });

  it('muestra la ayuda al seleccionar la herramienta de polígono', () => {
    setup({ tool: 'polygon' });
    expect(screen.getByText(/doble clic/i)).toBeInTheDocument();
  });
});
