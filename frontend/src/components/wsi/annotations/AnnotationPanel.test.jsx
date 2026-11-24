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
    expect(screen.getByText('(sin nombre)')).toBeInTheDocument();
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

  it('llama a onExportCoco y onImportCoco desde los botones', () => {
    const onExportCoco = vi.fn();
    const onImportCoco = vi.fn();
    render(
      <AnnotationPanel
        annotations={annotations}
        classes={classes}
        loading={false}
        onExportCoco={onExportCoco}
        onImportCoco={onImportCoco}
      />
    );
    fireEvent.click(screen.getByTitle('Importar anotaciones COCO'));
    fireEvent.click(screen.getByTitle('Exportar anotaciones COCO'));
    expect(onImportCoco).toHaveBeenCalled();
    expect(onExportCoco).toHaveBeenCalled();
  });

  it('deshabilita exportar COCO cuando no hay anotaciones', () => {
    render(
      <AnnotationPanel annotations={[]} classes={[]} loading={false} />
    );
    expect(screen.getByTitle('Exportar anotaciones COCO')).toBeDisabled();
  });
});
