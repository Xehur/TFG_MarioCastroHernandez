/**
 * Utilidades generales
 */

/**
 * Formatea el tamaño de archivo en MB/GB
 */
export const formatFileSize = sizeInMB => {
  if (!sizeInMB && sizeInMB !== 0) {
    return 'N/A';
  }
  if (sizeInMB >= 1024) {
    return `${(sizeInMB / 1024).toFixed(2)} GB`;
  }
  return `${sizeInMB.toFixed(2)} MB`;
};

/**
 * Formatea una fecha a formato local
 */
export const formatDate = dateString => {
  const date = new Date(dateString);
  return date.toLocaleDateString('es-ES', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * Valida extensiones de archivos WSI permitidas
 */
export const isValidWSIFile = filename => {
  const allowedExtensions = ['.svs', '.tiff', '.tif', '.mrxs'];
  const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));
  return allowedExtensions.includes(extension);
};
