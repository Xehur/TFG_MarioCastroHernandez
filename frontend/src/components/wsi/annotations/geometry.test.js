import { describe, it, expect, vi } from 'vitest';
import {
  imageToElement,
  elementToImage,
  imageDistanceToElement,
  annotationCenter,
  centerOnAnnotation,
  getImageSize,
} from './geometry';

// Visor falso con una transformación determinista:
// imagen -> viewport: identidad; viewport -> pixel: multiplica por 2.
const makeViewer = () => {
  const panTo = vi.fn();
  const applyConstraints = vi.fn();
  return {
    viewer: {
      viewport: {
        imageToViewportCoordinates: p => p,
        pixelFromPoint: vp => ({ x: vp.x * 2, y: vp.y * 2 }),
        pointFromPixel: p => ({ x: p.x / 2, y: p.y / 2 }),
        viewportToImageCoordinates: vp => ({ x: vp.x, y: vp.y }),
        panTo,
        applyConstraints,
      },
      world: {
        getItemAt: () => ({ getContentSize: () => ({ x: 1000, y: 800 }) }),
      },
    },
    panTo,
    applyConstraints,
  };
};

describe('geometry', () => {
  it('imageToElement aplica la transformación del viewport', () => {
    const { viewer } = makeViewer();
    expect(imageToElement(viewer, 3, 4)).toEqual({ x: 6, y: 8 });
  });

  it('elementToImage invierte la transformación', () => {
    const { viewer } = makeViewer();
    expect(elementToImage(viewer, 6, 8)).toEqual({ x: 3, y: 4 });
  });

  it('imageDistanceToElement escala una distancia', () => {
    const { viewer } = makeViewer();
    expect(imageDistanceToElement(viewer, 10)).toBe(20);
  });

  it('getImageSize devuelve el tamaño de la imagen', () => {
    const { viewer } = makeViewer();
    expect(getImageSize(viewer)).toEqual({ width: 1000, height: 800 });
  });

  describe('annotationCenter', () => {
    it('rectángulo', () => {
      expect(
        annotationCenter({
          shape_type: 'rectangle',
          coordinates: { x: 10, y: 20, width: 100, height: 40 },
        })
      ).toEqual({ x: 60, y: 40 });
    });

    it('círculo', () => {
      expect(
        annotationCenter({ shape_type: 'circle', coordinates: { x: 5, y: 6, radius: 3 } })
      ).toEqual({ x: 5, y: 6 });
    });

    it('polígono (centroide)', () => {
      expect(
        annotationCenter({
          shape_type: 'polygon',
          coordinates: { points: [[0, 0], [10, 0], [10, 10], [0, 10]] },
        })
      ).toEqual({ x: 5, y: 5 });
    });

    it('devuelve null para formas desconocidas', () => {
      expect(annotationCenter({ shape_type: 'star', coordinates: {} })).toBeNull();
    });
  });

  it('centerOnAnnotation hace pan al centro', () => {
    const { viewer, panTo, applyConstraints } = makeViewer();
    centerOnAnnotation(viewer, {
      shape_type: 'circle',
      coordinates: { x: 1, y: 2, radius: 1 },
    });
    expect(panTo).toHaveBeenCalled();
    expect(applyConstraints).toHaveBeenCalled();
  });
});
