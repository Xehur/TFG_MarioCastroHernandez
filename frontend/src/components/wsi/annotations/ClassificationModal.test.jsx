import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ClassificationModal from './ClassificationModal';

const classes = [
  { id: 10, name: 'Tumor', color: '#FF0000' },
  { id: 11, name: 'Necrosis', color: '#00FF00' },
];

const baseProps = {
  shape: { shape_type: 'rectangle' },
  classes,
  defaultColor: '#FF0000',
  onCreateClass: vi.fn(),
  onSubmit: vi.fn().mockResolvedValue(undefined),
  onCancel: vi.fn(),
};

describe('ClassificationModal', () => {
  it('renderiza el título y el tipo de forma', () => {
    render(<ClassificationModal {...baseProps} />);
    expect(screen.getByText('Nueva anotación')).toBeInTheDocument();
    expect(screen.getByText(/Rectángulo/i)).toBeInTheDocument();
  });

  it('envía la etiqueta y la clase seleccionada', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ClassificationModal {...baseProps} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Nombre de la anotación'), { target: { value: 'Mi zona' } });
    fireEvent.change(screen.getByLabelText('Clasificación (opcional)'), { target: { value: '10' } });
    fireEvent.click(screen.getByText('Guardar'));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ label: 'Mi zona', class_id: 10 })
    );
  });

  it('guarda una anotación solo con nombre, sin clasificación', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ClassificationModal {...baseProps} onSubmit={onSubmit} />);

    expect(screen.getByLabelText('Clasificación (opcional)')).toHaveValue('');
    expect(screen.getByText(/solo con su nombre/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Nombre de la anotación'), {
      target: { value: 'Zona de interés' },
    });
    fireEvent.click(screen.getByText('Guardar'));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ label: 'Zona de interés', class_id: null })
    );
  });

  it('exige un nombre o una clasificación', () => {
    const onSubmit = vi.fn();
    render(<ClassificationModal {...baseProps} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText('Guardar'));
    expect(screen.getByRole('alert')).toHaveTextContent('Escribe un nombre o elige');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('cancela con el botón Cancelar', () => {
    const onCancel = vi.fn();
    render(<ClassificationModal {...baseProps} onCancel={onCancel} />);
    fireEvent.click(screen.getByText('Cancelar'));
    expect(onCancel).toHaveBeenCalled();
  });

  it('precarga valores en modo edición', () => {
    render(
      <ClassificationModal
        {...baseProps}
        initialLabel="Existente"
        initialClassId={11}
        initialColor="#123456"
        title="Editar anotación"
        submitLabel="Guardar cambios"
      />
    );
    expect(screen.getByText('Editar anotación')).toBeInTheDocument();
    expect(screen.getByLabelText('Nombre de la anotación')).toHaveValue('Existente');
    expect(screen.getByLabelText('Clasificación (opcional)')).toHaveValue('11');
    expect(screen.getByText('Guardar cambios')).toBeInTheDocument();
  });

  it('permite crear una nueva clase', async () => {
    const onCreateClass = vi.fn().mockResolvedValue({ id: 99, name: 'Estroma', color: '#abcdef' });
    render(<ClassificationModal {...baseProps} onCreateClass={onCreateClass} />);

    fireEvent.click(screen.getByText('+ Nueva clase'));
    fireEvent.change(screen.getByPlaceholderText('Nombre de la clase'), {
      target: { value: 'Estroma' },
    });
    fireEvent.click(screen.getByText('Crear'));

    await waitFor(() => expect(onCreateClass).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Estroma' })
    ));
  });
});
