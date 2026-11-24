import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Register from './Register';
import { normalizeApiError } from '../../utils/apiError';

const registerMock = vi.fn();
vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({ register: registerMock }),
}));

const fillAndSubmit = (email = 'a@ejemplo.test', password = 'secreto1') => {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: 'Registrarse' }));
};

describe('Register', () => {
  beforeEach(() => {
    registerMock.mockReset();
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );
  });

  it('muestra el motivo de validación que devuelve el servidor (422)', async () => {
    // Error tal y como lo entrega el interceptor de api.js
    registerMock.mockRejectedValue(
      normalizeApiError({
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
      })
    );
    fillAndSubmit();
    expect(await screen.findByText(/dominio está reservado/)).toBeInTheDocument();
  });

  it('muestra los errores de negocio del servidor (email ya registrado)', async () => {
    registerMock.mockRejectedValue(
      normalizeApiError({
        response: { status: 400, data: { detail: 'El email ya está registrado' } },
      })
    );
    fillAndSubmit('ya@example.com');
    expect(await screen.findByText('El email ya está registrado')).toBeInTheDocument();
  });

  it('usa el mensaje genérico si el error no trae texto', async () => {
    registerMock.mockRejectedValue({});
    fillAndSubmit('b@example.com');
    expect(await screen.findByText('No se pudo completar el registro.')).toBeInTheDocument();
  });
});
