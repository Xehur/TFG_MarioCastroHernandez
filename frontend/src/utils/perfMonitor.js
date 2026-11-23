/**
 * Monitor de rendimiento para el visor WSI.
 *
 * Mide la carga de tiles (cantidad, fallos y duración) enganchándose a los
 * eventos de OpenSeadragon. En desarrollo registra un resumen en consola.
 * Devuelve un objeto con `getStats()` y `destroy()`.
 */
import config from '../config/config';

export const createPerfMonitor = viewer => {
  const stats = {
    tilesLoaded: 0,
    tilesFailed: 0,
    cacheHits: 0,
    totalLoadMs: 0,
    lastReset: performance.now(),
  };

  // Marca de tiempo por tile en descarga (clave: url)
  const pending = new Map();

  const onTileLoadStart = event => {
    if (event?.tile?.url) {
      pending.set(event.tile.url, performance.now());
    }
  };

  const onTileLoaded = event => {
    stats.tilesLoaded += 1;
    const url = event?.tile?.url;
    if (url && pending.has(url)) {
      stats.totalLoadMs += performance.now() - pending.get(url);
      pending.delete(url);
    }
    // El backend indica si el tile vino de su caché
    const cacheHeader = event?.tileRequest?.getResponseHeader?.('X-Tile-Cache');
    if (cacheHeader === 'HIT') {
      stats.cacheHits += 1;
    }
  };

  const onTileFailed = () => {
    stats.tilesFailed += 1;
  };

  viewer.addHandler('tile-load-start', onTileLoadStart);
  viewer.addHandler('tile-loaded', onTileLoaded);
  viewer.addHandler('tile-load-failed', onTileFailed);

  const getStats = () => {
    const avgLoadMs = stats.tilesLoaded > 0 ? stats.totalLoadMs / stats.tilesLoaded : 0;
    return {
      ...stats,
      avgLoadMs: Math.round(avgLoadMs),
    };
  };

  // En desarrollo, log periódico del resumen
  let intervalId = null;
  if (config.isDevelopment) {
    intervalId = setInterval(() => {
      if (stats.tilesLoaded === 0 && stats.tilesFailed === 0) return;
      const s = getStats();
      console.info(
        `[WSI perf] tiles=${s.tilesLoaded} fallos=${s.tilesFailed} ` +
          `cacheHits=${s.cacheHits} avgLoad=${s.avgLoadMs}ms`
      );
    }, 5000);
  }

  const destroy = () => {
    if (intervalId) clearInterval(intervalId);
    viewer.removeHandler('tile-load-start', onTileLoadStart);
    viewer.removeHandler('tile-loaded', onTileLoaded);
    viewer.removeHandler('tile-load-failed', onTileFailed);
    pending.clear();
  };

  return { getStats, destroy };
};
