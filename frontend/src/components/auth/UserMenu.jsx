import { User } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import './UserMenu.css';

/**
 * Muestra el usuario autenticado y un botón para cerrar sesión.
 */
const UserMenu = () => {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div className="user-menu">
      <span className="user-menu-email" title={user.email}>
        <User size={16} /> {user.full_name || user.email}
      </span>
      <button className="user-menu-logout" onClick={logout} type="button">
        Cerrar sesión
      </button>
    </div>
  );
};

export default UserMenu;
