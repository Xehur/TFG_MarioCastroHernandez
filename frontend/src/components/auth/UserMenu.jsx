import { User, Settings } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import './UserMenu.css';

/**
 * Muestra el usuario autenticado, acceso a ajustes y botón para cerrar sesión.
 */
const UserMenu = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  return (
    <div className="user-menu">
      <button
        className="user-menu-email"
        title="Ajustes de la cuenta"
        onClick={() => navigate('/settings')}
        type="button"
      >
        <User size={16} /> {user.full_name || user.email}
        <Settings size={15} className="user-menu-gear" />
      </button>
      <button className="user-menu-logout" onClick={logout} type="button">
        Cerrar sesión
      </button>
    </div>
  );
};

export default UserMenu;
