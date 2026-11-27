/** Top navigation: links, the cart count, and who is signed in. */

import { Link, NavLink } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';
import { useCart } from '../cart/useCart';

export default function NavBar() {
  const { user, isAuthenticated, logout, profileComplete } = useAuth();
  const { itemCount } = useCart();

  // A customer whose profile is short of a phone number or an address cannot
  // check out. Flagging it on the avatar means they find out while browsing
  // rather than at the last step of a purchase.
  const needsDetails = isAuthenticated && !user?.is_organization && !profileComplete;

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
              <NavLink
                to="/profile"
                className="navbar__identity"
                title={
                  needsDetails
                    ? 'Your profile needs a phone number and address'
                    : 'Your profile'
                }
              >
                <span className="navbar__avatar" aria-hidden="true">
                  {user.username.charAt(0).toUpperCase()}
                </span>
                <span className="navbar__user">{user.username}</span>
                {needsDetails && (
                  <span className="navbar__dot" aria-hidden="true" />
                )}
                {needsDetails && (
                  <span className="visually-hidden">
                    — details needed before you can order
                  </span>
                )}
              </NavLink>
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
