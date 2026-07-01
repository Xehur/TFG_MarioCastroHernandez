import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

vi.mock('../../../services/annotationService', () => ({
  annotationService: {
    list: vi.fn(),
    listClasses: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    createClass: vi.fn(),
    importCoco: vi.fn(),
  },
}));

import { annotationService } from '../../../services/annotationService';
import { useAnnotations } from './useAnnotations';

describe('useAnnotations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    annotationService.list.mockResolvedValue({ total: 1, items: [{ id: 1, label: 'a' }] });
    annotationService.listClasses.mockResolvedValue([{ id: 10, name: 'Tumor' }]);
  });

  it('carga anotaciones y clases al montar', async () => {
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.annotations).toHaveLength(1);
    expect(result.current.classes).toHaveLength(1);
  });

  it('createAnnotation añade la anotación al estado', async () => {
    annotationService.create.mockResolvedValue({ id: 2, label: 'nueva' });
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createAnnotation({ shape_type: 'circle', coordinates: {} });
    });
    expect(result.current.annotations).toHaveLength(2);
  });

  it('updateAnnotation reemplaza la anotación', async () => {
    annotationService.update.mockResolvedValue({ id: 1, label: 'editada' });
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.updateAnnotation(1, { label: 'editada' });
    });
    expect(result.current.annotations[0].label).toBe('editada');
  });

  it('deleteAnnotation elimina la anotación', async () => {
    annotationService.remove.mockResolvedValue({});
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteAnnotation(1);
    });
    expect(result.current.annotations).toHaveLength(0);
  });

  it('createClass añade la clase', async () => {
    annotationService.createClass.mockResolvedValue({ id: 11, name: 'Necrosis' });
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createClass({ name: 'Necrosis', color: '#0f0' });
    });
    expect(result.current.classes).toHaveLength(2);
  });

  it('importCoco importa y recarga las anotaciones', async () => {
    annotationService.importCoco.mockResolvedValue({
      imported: 2,
      created_classes: ['Necrosis'],
    });
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));

    annotationService.list.mockResolvedValue({
      total: 3,
      items: [{ id: 1 }, { id: 2 }, { id: 3 }],
    });

    let res;
    await act(async () => {
      res = await result.current.importCoco({ images: [], annotations: [] });
    });
    expect(annotationService.importCoco).toHaveBeenCalledWith(
      5,
      { images: [], annotations: [] },
      null
    );
    expect(res.imported).toBe(2);
    expect(result.current.annotations).toHaveLength(3);
  });

  it('guarda el error si falla la carga', async () => {
    annotationService.list.mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useAnnotations(5));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('boom');
  });
});
