import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AnnotationPanel from './AnnotationPanel';

const annotations = [
  { id: 1, shape_type: 'rectangle', label: 'Zona A', color: '#FF0000', class_id: 10 },
  { id: 2, shape_type: 'circle', label: null, color: '#00FF00', class_id: null },
];
const classes = [{ id: 10, name: 'Tumor' }];

describe('AnnotationPanel', () => {
  it('muestra el estado vacío sin anotaciones', () => {
    render(<AnnotationPanel annotations={[]} classes={[]} loading={false} />);
    expect(screen.getByText(/No hay anotaciones/i)).toBeInTheDocument();
  });

  it('muestra el indicador de carga', () => {
    render(<AnnotationPanel annotations={[]} classes={[]} loading={true} />);
    expect(screen.getByText(/Cargando/i)).toBeInTheDocument();
  });

  it('lista las anotaciones con etiqueta y clase', () => {
    render(<AnnotationPanel annotations={annotations} classes={classes} loading={false} />);
    expect(screen.getByText('Zona A')).toBeInTheDocument();
    expect(screen.getByText('Tumor')).toBeInTheDocument();
    expect(screen.getByText('(sin etiqueta)')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // contador
  });

  it('llama a onSelect al hacer clic en una anotación', () => {
    const onSelect = vi.fn();
    render(
      <AnnotationPanel
        annotations={annotations}
        classes={classes}
        loading={false}
        onSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByText('Zona A'));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it('llama a onCenter, onEdit y onDelete desde los botones', () => {
    const onCenter = vi.fn();
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    render(
      <AnnotationPanel
        annotations={annotations}
        classes={classes}
        loading={false}
        onCenter={onCenter}
        onEdit={onEdit}
        onDelete={onDelete}
      />
    );
    fireEvent.click(screen.getAllByTitle('Centrar')[0]);
    fireEvent.click(screen.getAllByTitle('Editar')[0]);
    fireEvent.click(screen.getAllByTitle('Eliminar')[0]);
    expect(onCenter).toHaveBeenCalledWith(annotations[0]);
    expect(onEdit).toHaveBeenCalledWith(annotations[0]);
    expect(onDelete).toHaveBeenCalledWith(1);
  });
});
