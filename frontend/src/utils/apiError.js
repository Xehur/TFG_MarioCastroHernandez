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

/** Nombres legibles de los campos que valida el backend. */
const FIELD_LABELS = {
  email: 'Email',
  password: 'Contraseña',
  full_name: 'Nombre completo',
  current_password: 'Contraseña actual',
  new_password: 'Nueva contraseña',
};

/**
 * Traduce un error de validación de Pydantic (FastAPI, status 422) a un
 * mensaje en español. Si el tipo no es conocido, conserva el mensaje original.
 */
export const formatValidationItem = item => {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return null;

  const loc = Array.isArray(item.loc) ? item.loc : [];
  const field = [...loc].reverse().find(part => typeof part === 'string' && part !== 'body');
  const label = field ? FIELD_LABELS[field] || field : null;
  const msg = item.msg || '';
  const ctx = item.ctx || {};

  if (field === 'email' || /email address/i.test(msg)) {
    if (/special-use or reserved/i.test(msg)) {
      return 'Email: el dominio está reservado para usos especiales (por ejemplo, .test o .local) y no puede utilizarse';
    }
    if (item.type === 'missing') return 'Email: campo obligatorio';
    return 'Email: la dirección no es válida. Comprueba que tenga el formato nombre@dominio.com';
  }

  const prefix = label ? `${label}: ` : '';
  switch (item.type) {
    case 'missing':
      return `${prefix}campo obligatorio`;
    case 'string_too_short':
      return `${prefix}debe tener al menos ${ctx.min_length} caracteres`;
    case 'string_too_long':
      return `${prefix}no puede superar los ${ctx.max_length} caracteres`;
    default:
      return msg ? `${prefix}${msg}` : null;
  }
};

/**
 * Extrae un mensaje legible del campo `detail` de FastAPI,
 * que puede ser un string o un array de errores de validación.
 */
const extractDetailMessage = detail => {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(formatValidationItem).filter(Boolean).join('; ') || null;
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
