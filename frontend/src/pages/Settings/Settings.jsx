import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, UserCog, Save, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { authService } from '../../services/authService';
import './Settings.css';

/**
 * Página de ajustes de la cuenta: permite modificar nombre, email y contraseña
 * del usuario autenticado.
 */
const Settings = () => {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async e => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const wantsPasswordChange = Boolean(newPassword || confirmPassword || currentPassword);

    if (wantsPasswordChange) {
      if (!currentPassword) {
        setError('Introduce tu contraseña actual para cambiarla.');
        return;
      }
      if (newPassword.length < 6) {
        setError('La nueva contraseña debe tener al menos 6 caracteres.');
        return;
      }
      if (newPassword !== confirmPassword) {
        setError('La nueva contraseña y su confirmación no coinciden.');
        return;
      }
    }

    const payload = {};
    if (fullName !== (user?.full_name || '')) payload.fullName = fullName;
    if (email !== (user?.email || '')) payload.email = email;
    if (wantsPasswordChange) {
      payload.currentPassword = currentPassword;
      payload.newPassword = newPassword;
    }

    if (Object.keys(payload).length === 0) {
      setError('No hay cambios que guardar.');
      return;
    }

    setSubmitting(true);
    try {
      const updated = await authService.updateProfile(payload);
      updateUser(updated);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setSuccess('Cambios guardados correctamente.');
    } catch (err) {
      const detail = err.response?.data?.detail || 'No se pudieron guardar los cambios.';
      setError(typeof detail === 'string' ? detail : 'Error al guardar los cambios.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-container">
        <button className="settings-back" onClick={() => navigate('/')} type="button">
          <ArrowLeft size={18} /> Volver
        </button>

        <div className="settings-card">
          <div className="settings-head">
            <div className="settings-logo">
              <UserCog size={26} />
            </div>
            <h1>Ajustes de la cuenta</h1>
            <p className="settings-subtitle">Gestiona tu perfil y credenciales</p>
          </div>

          <form className="settings-form" onSubmit={handleSubmit}>
            {error && <div className="settings-error">{error}</div>}
            {success && (
              <div className="settings-success">
                <CheckCircle2 size={16} /> {success}
              </div>
            )}

            <section className="settings-section">
              <h2>Perfil</h2>
              <div className="settings-field">
                <label htmlFor="fullName">Nombre completo</label>
                <input
                  id="fullName"
                  type="text"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  autoComplete="name"
                />
              </div>
              <div className="settings-field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </div>
            </section>

            <section className="settings-section">
              <h2>Cambiar contraseña</h2>
              <p className="settings-hint">Déjalo en blanco si no quieres cambiarla.</p>
              <div className="settings-field">
                <label htmlFor="currentPassword">Contraseña actual</label>
                <input
                  id="currentPassword"
                  type="password"
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </div>
              <div className="settings-field">
                <label htmlFor="newPassword">Nueva contraseña</label>
                <input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                />
              </div>
              <div className="settings-field">
                <label htmlFor="confirmPassword">Confirmar nueva contraseña</label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                />
              </div>
            </section>

            <button className="settings-button" type="submit" disabled={submitting}>
              <Save size={16} /> {submitting ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Settings;
