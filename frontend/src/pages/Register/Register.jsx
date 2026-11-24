import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Microscope } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import '../../components/auth/Auth.css';

/**
 * Página de registro de usuario.
 */
const Register = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async e => {
    e.preventDefault();
    setError(null);

    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres.');
      return;
    }

    setSubmitting(true);
    try {
      await register({ email, password, fullName });
      navigate('/', { replace: true });
    } catch (err) {
      // El interceptor de api.js entrega un ApiError con el motivo ya legible.
      setError(err?.message || 'No se pudo completar el registro.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card-head">
          <div className="auth-card-logo">
            <Microscope size={26} />
          </div>
          <h1>Crear cuenta</h1>
          <p className="auth-subtitle">Visor de imágenes WSI</p>
        </div>
        <form className="auth-form" onSubmit={handleSubmit}>
          {error && <div className="auth-error">{error}</div>}
          <div className="auth-field">
            <label htmlFor="fullName">Nombre completo</label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              autoComplete="name"
            />
          </div>
          <div className="auth-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="auth-field">
            <label htmlFor="password">Contraseña</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete="new-password"
            />
          </div>
          <button className="auth-button" type="submit" disabled={submitting}>
            {submitting ? 'Creando…' : 'Registrarse'}
          </button>
        </form>
        <p className="auth-footer">
          ¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link>
        </p>
      </div>
    </div>
  );
};

export default Register;
