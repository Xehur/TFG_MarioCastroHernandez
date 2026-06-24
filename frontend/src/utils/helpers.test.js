import { describe, it, expect } from 'vitest';
import { formatFileSize, formatDate, isValidWSIFile } from './helpers';

describe('helpers', () => {
  describe('formatFileSize', () => {
    it('devuelve N/A para valores nulos', () => {
      expect(formatFileSize(null)).toBe('N/A');
      expect(formatFileSize(undefined)).toBe('N/A');
    });

    it('formatea MB', () => {
      expect(formatFileSize(83.4)).toBe('83.40 MB');
      expect(formatFileSize(0)).toBe('0.00 MB');
    });

    it('formatea GB cuando supera 1024 MB', () => {
      expect(formatFileSize(2048)).toBe('2.00 GB');
    });
  });

  describe('isValidWSIFile', () => {
    it('acepta extensiones válidas', () => {
      expect(isValidWSIFile('imagen.svs')).toBe(true);
      expect(isValidWSIFile('IMAGEN.TIFF')).toBe(true);
      expect(isValidWSIFile('a.tif')).toBe(true);
      expect(isValidWSIFile('b.mrxs')).toBe(true);
    });

    it('rechaza extensiones no válidas', () => {
      expect(isValidWSIFile('foto.jpg')).toBe(false);
      expect(isValidWSIFile('doc.pdf')).toBe(false);
    });
  });

  describe('formatDate', () => {
    it('formatea una fecha ISO sin lanzar error', () => {
      const out = formatDate('2024-01-15T10:30:00Z');
      expect(typeof out).toBe('string');
      expect(out.length).toBeGreaterThan(0);
    });
  });
});
