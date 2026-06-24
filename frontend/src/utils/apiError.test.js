import { describe, it, expect } from 'vitest';
import { ApiError, normalizeApiError } from './apiError';

describe('normalizeApiError', () => {
  it('usa el detalle string de la respuesta', () => {
    const err = normalizeApiError({ response: { status: 400, data: { detail: 'Mal' } } });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe('Mal');
  });

  it('une los mensajes de un array de validación (422)', () => {
    const err = normalizeApiError({
      response: {
        status: 422,
        data: { detail: [{ msg: 'campo x' }, { msg: 'campo y' }] },
      },
    });
    expect(err.message).toBe('campo x; campo y');
  });

  it('usa el mensaje por defecto del status si no hay detalle', () => {
    const err = normalizeApiError({ response: { status: 401, data: {} } });
    expect(err.message).toContain('autorizado');
    expect(err.status).toBe(401);
  });

  it('detecta error de red', () => {
    const err = normalizeApiError({ request: {} });
    expect(err.code).toBe('NETWORK_ERROR');
  });

  it('error desconocido', () => {
    const err = normalizeApiError({ message: 'boom' });
    expect(err.code).toBe('UNKNOWN');
    expect(err.message).toBe('boom');
  });
});
