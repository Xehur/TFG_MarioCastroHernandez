import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock del cliente axios
vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import apiClient from './api';
import { annotationService } from './annotationService';

describe('annotationService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('list() pide las anotaciones de una imagen con paginación', async () => {
    apiClient.get.mockResolvedValue({ data: { total: 0, items: [] } });
    const result = await annotationService.list(5);
    expect(apiClient.get).toHaveBeenCalledWith('/images/5/annotations', {
      params: { skip: 0, limit: 500 },
    });
    expect(result).toEqual({ total: 0, items: [] });
  });

  it('create() envía la anotación al endpoint correcto', async () => {
    const payload = { shape_type: 'rectangle', coordinates: {} };
    apiClient.post.mockResolvedValue({ data: { id: 1, ...payload } });
    const result = await annotationService.create(7, payload);
    expect(apiClient.post).toHaveBeenCalledWith('/images/7/annotations', payload);
    expect(result.id).toBe(1);
  });

  it('update() hace PUT sobre /annotations/:id', async () => {
    apiClient.put.mockResolvedValue({ data: { id: 3, label: 'x' } });
    const result = await annotationService.update(3, { label: 'x' });
    expect(apiClient.put).toHaveBeenCalledWith('/annotations/3', { label: 'x' });
    expect(result.label).toBe('x');
  });

  it('remove() hace DELETE sobre /annotations/:id', async () => {
    apiClient.delete.mockResolvedValue({ data: { message: 'ok' } });
    await annotationService.remove(9);
    expect(apiClient.delete).toHaveBeenCalledWith('/annotations/9');
  });

  it('listClasses() pide las clases de anotación', async () => {
    apiClient.get.mockResolvedValue({ data: [{ id: 1, name: 'Tumor' }] });
    const result = await annotationService.listClasses();
    expect(apiClient.get).toHaveBeenCalledWith('/annotation-classes');
    expect(result).toHaveLength(1);
  });

  it('createClass() crea una clase', async () => {
    const payload = { name: 'Necrosis', color: '#00FF00' };
    apiClient.post.mockResolvedValue({ data: { id: 2, ...payload } });
    const result = await annotationService.createClass(payload);
    expect(apiClient.post).toHaveBeenCalledWith('/annotation-classes', payload);
    expect(result.id).toBe(2);
  });

  it('deleteClass() elimina una clase', async () => {
    apiClient.delete.mockResolvedValue({ data: { message: 'ok' } });
    await annotationService.deleteClass(4);
    expect(apiClient.delete).toHaveBeenCalledWith('/annotation-classes/4');
  });

  it('exportCoco() pide el COCO de una imagen', async () => {
    apiClient.get.mockResolvedValue({ data: { images: [], annotations: [] } });
    const result = await annotationService.exportCoco(8);
    expect(apiClient.get).toHaveBeenCalledWith('/images/8/export/coco');
    expect(result).toHaveProperty('annotations');
  });

  it('importCoco() envía el documento y el mapeo de categorías', async () => {
    const coco = { images: [], annotations: [], categories: [] };
    apiClient.post.mockResolvedValue({ data: { imported: 0, created_classes: [] } });
    await annotationService.importCoco(3, coco, { cell: 'Célula' });
    expect(apiClient.post).toHaveBeenCalledWith('/images/3/import/coco', {
      coco,
      category_mapping: { cell: 'Célula' },
    });
  });

  it('importCoco() usa null como mapeo por defecto', async () => {
    const coco = { images: [], annotations: [], categories: [] };
    apiClient.post.mockResolvedValue({ data: { imported: 0 } });
    await annotationService.importCoco(3, coco);
    expect(apiClient.post).toHaveBeenCalledWith('/images/3/import/coco', {
      coco,
      category_mapping: null,
    });
  });
});
