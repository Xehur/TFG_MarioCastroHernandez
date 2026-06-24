import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Microscope, Layers, ScanSearch, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import '../../components/auth/Auth.css';

/**
 * Página de inicio de sesión.
 */
const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async e => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate(from, { replace: true });
    } catch (err) {
      const detail =
        err.response?.data?.detail || 'No se pudo iniciar sesión. Revisa tus credenciales.';
      setError(typeof detail === 'string' ? detail : 'Error de autenticación.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page auth-split">
      <aside className="auth-hero">
        <div className="auth-hero-overlay" />
        <div className="auth-hero-content">
          <div className="auth-brand">
            <div className="auth-brand-logo">
              <Microscope size={44} />
            </div>
            <span className="auth-brand-name">WSI Viewer</span>
          </div>
          <h2 className="auth-hero-title">
            Explora imágenes histológicas con precisión clínica
          </h2>
          <p className="auth-hero-text">
            Visualiza, anota y clasifica Whole Slide Images de alta resolución desde tu navegador.
          </p>
          <ul className="auth-hero-features">
            <li>
              <ScanSearch size={18} /> Zoom fluido por niveles
            </li>
            <li>
              <Layers size={18} /> Anotaciones y clasificación
            </li>
            <li>
              <ShieldCheck size={18} /> Acceso autenticado con token
            </li>
          </ul>
        </div>
      </aside>

      <div className="auth-card">
        <div className="auth-card-head">
          <div className="auth-card-logo">
            <Microscope size={26} />
          </div>
          <h1>Iniciar sesión</h1>
          <p className="auth-subtitle">Accede a tu visor de imágenes WSI</p>
        </div>
        <form className="auth-form" onSubmit={handleSubmit}>
          {error && <div className="auth-error">{error}</div>}
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
              autoComplete="current-password"
            />
          </div>
          <button className="auth-button" type="submit" disabled={submitting}>
            {submitting ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
        <p className="auth-footer">
          ¿No tienes cuenta? <Link to="/register">Regístrate</Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
