import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AnalysisProgress from './AnalysisProgress';

describe('AnalysisProgress', () => {
  it('muestra el porcentaje y la barra de progreso', () => {
    render(<AnalysisProgress progress={42} elapsedMs={3000} onCancel={vi.fn()} />);
    expect(screen.getByText('42%')).toBeInTheDocument();
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '42');
    expect(screen.getByText(/transcurrido/)).toBeInTheDocument();
  });

  it('muestra estimación restante cuando hay progreso suficiente', () => {
    render(<AnalysisProgress progress={50} elapsedMs={5000} onCancel={vi.fn()} />);
    expect(screen.getByText(/restante/)).toBeInTheDocument();
  });

  it('no muestra estimación con progreso muy bajo', () => {
    render(<AnalysisProgress progress={1} elapsedMs={100} onCancel={vi.fn()} />);
    expect(screen.queryByText(/restante/)).not.toBeInTheDocument();
  });

  it('formatea minutos y segundos para tiempos largos', () => {
    render(<AnalysisProgress progress={30} elapsedMs={95000} onCancel={vi.fn()} />);
    expect(screen.getByText(/1m 35s transcurrido/)).toBeInTheDocument();
  });

  it('llama a onCancel al pulsar Cancelar', () => {
    const onCancel = vi.fn();
    render(<AnalysisProgress progress={30} elapsedMs={1000} onCancel={onCancel} />);
    fireEvent.click(screen.getByText(/Cancelar/));
    expect(onCancel).toHaveBeenCalled();
  });
});
