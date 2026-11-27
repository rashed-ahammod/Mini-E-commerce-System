/** Top navigation: links, the cart count, and who is signed in. */

import { Link, NavLink } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';
import { useCart } from '../cart/useCart';

export default function NavBar() {
  const { user, isAuthenticated, logout } = useAuth();
  const { itemCount } = useCart();

  return (
    <header className="navbar">
      <div className="navbar__inner">
        <Link to="/" className="navbar__brand">
          Mini<span>Shop</span>
        </Link>

        <nav className="navbar__links">
          <NavLink to="/" end>
            Products
          </NavLink>
          <NavLink to="/cart">
            Cart
            {itemCount > 0 && <span className="badge">{itemCount}</span>}
          </NavLink>
          {isAuthenticated && <NavLink to="/orders">My orders</NavLink>}
          {/* Only organization accounts are shown the way in; a customer
              would only reach a redirect. */}
          {user?.is_organization && (
            <NavLink to="/org" className="navbar__ops">
              Operations
            </NavLink>
          )}
        </nav>

        <div className="navbar__account">
          {isAuthenticated ? (
            <>
              <span className="navbar__user">{user.username}</span>
              <button type="button" className="button button--ghost" onClick={logout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className="button button--ghost">
                Log in
              </NavLink>
              <NavLink to="/register" className="button">
                Sign up
              </NavLink>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
