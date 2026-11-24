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

  it('traduce el email con dominio reservado (p. ej. .test)', () => {
    const err = normalizeApiError({
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: 'value_error',
              loc: ['body', 'email'],
              msg: 'value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email.',
            },
          ],
        },
      },
    });
    expect(err.message).toContain('dominio está reservado');
    expect(err.message).not.toMatch(/value is not/);
  });

  it('traduce un email mal escrito y una contraseña corta a la vez', () => {
    const err = normalizeApiError({
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: 'value_error',
              loc: ['body', 'email'],
              msg: "value is not a valid email address: The part after the @-sign contains invalid characters: '@'.",
            },
            {
              type: 'string_too_short',
              loc: ['body', 'password'],
              msg: 'String should have at least 6 characters',
              ctx: { min_length: 6 },
            },
          ],
        },
      },
    });
    expect(err.message).toBe(
      'Email: la dirección no es válida. Comprueba que tenga el formato nombre@dominio.com; ' +
        'Contraseña: debe tener al menos 6 caracteres'
    );
  });

  it('traduce un campo obligatorio y conserva mensajes de tipo desconocido', () => {
    const err = normalizeApiError({
      response: {
        status: 422,
        data: {
          detail: [
            { type: 'missing', loc: ['body', 'email'], msg: 'Field required' },
            { type: 'otro', loc: ['body', 'full_name'], msg: 'raro' },
          ],
        },
      },
    });
    expect(err.message).toBe('Email: campo obligatorio; Nombre completo: raro');
  });

  it('usa el mensaje por defecto del 422 si el array no aporta texto', () => {
    const err = normalizeApiError({ response: { status: 422, data: { detail: [{}] } } });
    expect(err.message).toBe('Los datos enviados no son válidos.');
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
