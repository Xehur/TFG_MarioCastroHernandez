import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CocoImportModal from './CocoImportModal';

const validCoco = {
  images: [{ id: 1, file_name: 'a.svs', width: 10, height: 10 }],
  categories: [{ id: 1, name: 'Tumor' }],
  annotations: [
    {
      id: 1,
      image_id: 1,
      category_id: 1,
      bbox: [0, 0, 5, 5],
      attributes: { shape_type: 'rectangle' },
    },
  ],
};

function selectFile(content) {
  const input = document.querySelector('input[type="file"]');
  const file = new File([JSON.stringify(content)], 'test.json', {
    type: 'application/json',
  });
  fireEvent.change(input, { target: { files: [file] } });
}

describe('CocoImportModal', () => {
  it('muestra el nombre del archivo y la previsualización tras seleccionar', async () => {
    render(<CocoImportModal onImport={vi.fn()} onClose={vi.fn()} />);
    selectFile(validCoco);
    expect(await screen.findByText('test.json')).toBeInTheDocument();
    expect(
      await screen.findByText(/1 anotaciones · 1 categorías/)
    ).toBeInTheDocument();
    expect(screen.getByText(/rectangle: 1/)).toBeInTheDocument();
  });

  it('muestra un error con un archivo inválido', async () => {
    render(<CocoImportModal onImport={vi.fn()} onClose={vi.fn()} />);
    selectFile({ foo: 'bar' });
    expect(await screen.findByText(/Archivo inválido/)).toBeInTheDocument();
  });

  it('importa y muestra el resultado de éxito', async () => {
    const onImport = vi
      .fn()
      .mockResolvedValue({ imported: 1, created_classes: ['Tumor'] });
    render(<CocoImportModal onImport={onImport} onClose={vi.fn()} />);
    selectFile(validCoco);
    await screen.findByText(/1 anotaciones/);

    fireEvent.click(screen.getByRole('button', { name: /Importar/ }));

    await waitFor(() =>
      expect(screen.getByText(/Se importaron/)).toBeInTheDocument()
    );
    expect(onImport).toHaveBeenCalled();
    expect(screen.getByText(/Clases creadas: Tumor/)).toBeInTheDocument();
  });

  it('aplica el mapeo de categorías al importar', async () => {
    const onImport = vi.fn().mockResolvedValue({ imported: 1, created_classes: [] });
    render(<CocoImportModal onImport={onImport} onClose={vi.fn()} />);
    selectFile(validCoco);
    await screen.findByText(/1 anotaciones/);

    const input = screen.getByPlaceholderText('Tumor');
    fireEvent.change(input, { target: { value: 'Neoplasia' } });
    fireEvent.click(screen.getByRole('button', { name: /Importar/ }));

    await waitFor(() =>
      expect(onImport).toHaveBeenCalledWith(validCoco, { Tumor: 'Neoplasia' })
    );
  });

  it('llama a onClose al cancelar', async () => {
    const onClose = vi.fn();
    render(<CocoImportModal onImport={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /Cancelar/ }));
    expect(onClose).toHaveBeenCalled();
  });

  it('muestra el error del backend si la importación falla', async () => {
    const onImport = vi.fn().mockRejectedValue({
      response: { data: { detail: 'COCO inválido: falta clave' } },
    });
    render(<CocoImportModal onImport={onImport} onClose={vi.fn()} />);
    selectFile(validCoco);
    await screen.findByText(/1 anotaciones/);
    fireEvent.click(screen.getByRole('button', { name: /Importar/ }));
    await waitFor(() =>
      expect(screen.getByText(/COCO inválido: falta clave/)).toBeInTheDocument()
    );
  });
});
