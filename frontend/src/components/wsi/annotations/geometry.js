/**
 * Helpers de conversión de coordenadas entre el espacio de la imagen
 * (píxeles) y el espacio del elemento del visor (píxeles en pantalla),
 * usando la API de OpenSeadragon.
 */
import OpenSeadragon from 'openseadragon';

/** Convierte un punto en píxeles de imagen a píxeles del elemento del visor. */
export function imageToElement(viewer, x, y) {
  const vp = viewer.viewport.imageToViewportCoordinates(new OpenSeadragon.Point(x, y));
  const px = viewer.viewport.pixelFromPoint(vp, true);
  return { x: px.x, y: px.y };
}

/** Convierte un punto en píxeles del elemento del visor a píxeles de imagen. */
export function elementToImage(viewer, px, py) {
  const vp = viewer.viewport.pointFromPixel(new OpenSeadragon.Point(px, py), true);
  const img = viewer.viewport.viewportToImageCoordinates(vp);
  return { x: img.x, y: img.y };
}

/** Convierte una distancia en píxeles de imagen a píxeles del elemento. */
export function imageDistanceToElement(viewer, dist) {
  const a = imageToElement(viewer, 0, 0);
  const b = imageToElement(viewer, dist, 0);
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** Tamaño de la imagen (píxeles) o null si no está disponible. */
export function getImageSize(viewer) {
  const item = viewer.world.getItemAt(0);
  if (!item) return null;
  const size = item.getContentSize();
  return { width: size.x, height: size.y };
}

/** Calcula el centro (en píxeles de imagen) de una anotación. */
export function annotationCenter(annotation) {
  const { shape_type: shape, coordinates: c } = annotation;
  if (shape === 'rectangle') {
    return { x: c.x + c.width / 2, y: c.y + c.height / 2 };
  }
  if (shape === 'circle') {
    return { x: c.x, y: c.y };
  }
  if (shape === 'polygon' && Array.isArray(c.points) && c.points.length) {
    const sum = c.points.reduce((acc, p) => ({ x: acc.x + p[0], y: acc.y + p[1] }), { x: 0, y: 0 });
    return { x: sum.x / c.points.length, y: sum.y / c.points.length };
  }
  return null;
}

/** Centra el visor en una anotación dada (en coordenadas de imagen). */
export function centerOnAnnotation(viewer, annotation) {
  const c = annotationCenter(annotation);
  if (!c) return;
  const vp = viewer.viewport.imageToViewportCoordinates(new OpenSeadragon.Point(c.x, c.y));
  viewer.viewport.panTo(vp, false);
  viewer.viewport.applyConstraints();
}
