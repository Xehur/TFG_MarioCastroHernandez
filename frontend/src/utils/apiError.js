/**
 * Utilidades para el manejo estructurado de errores HTTP
 */

/**
 * Error normalizado de la API.
 * Expone status, code y details además del mensaje legible.
 */
export class ApiError extends Error {
  constructor(message, { status = null, code = null, details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const STATUS_MESSAGES = {
  400: 'Solicitud incorrecta. Revisa los datos enviados.',
  401: 'No estás autorizado. Inicia sesión de nuevo.',
  403: 'No tienes permisos para realizar esta acción.',
  404: 'El recurso solicitado no existe.',
  408: 'La solicitud ha tardado demasiado. Inténtalo de nuevo.',
  413: 'El archivo es demasiado grande.',
  415: 'Tipo de archivo no soportado.',
  422: 'Los datos enviados no son válidos.',
  429: 'Demasiadas peticiones. Espera un momento.',
  500: 'Error interno del servidor. Inténtalo más tarde.',
  502: 'Error de comunicación con el servidor.',
  503: 'El servicio no está disponible en este momento.',
};

/**
 * Extrae un mensaje legible del campo `detail` de FastAPI,
 * que puede ser un string o un array de errores de validación.
 */
const extractDetailMessage = detail => {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map(item => (typeof item === 'string' ? item : item.msg))
      .filter(Boolean)
      .join('; ');
  }
  return null;
};

/**
 * Convierte un error de Axios en un ApiError normalizado con un
 * mensaje legible en español.
 */
export const normalizeApiError = error => {
  if (error?.response) {
    const { status, data } = error.response;
    const detailMessage = extractDetailMessage(data?.detail);
    const message = detailMessage || STATUS_MESSAGES[status] || `Error del servidor (${status}).`;
    return new ApiError(message, { status, details: data?.detail ?? null });
  }

  if (error?.request) {
    return new ApiError('No se pudo conectar con el servidor. Verifica tu conexión.', {
      code: 'NETWORK_ERROR',
    });
  }

  return new ApiError(error?.message || 'Ha ocurrido un error inesperado.', {
    code: 'UNKNOWN',
  });
};
