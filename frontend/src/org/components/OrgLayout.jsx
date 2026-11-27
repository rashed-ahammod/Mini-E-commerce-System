/**
 * The frame around every organization page.
 *
 * It looks deliberately unlike the shop: a dark rail, its own navigation and
 * a visible "Operations" label. Someone who can both shop and run the shop
 * should never be in doubt about which one they are looking at — that is
 * what stops a test order being cancelled for real.
 */

import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../../auth/useAuth';

const LINKS = [
  { to: '/org', label: 'Dashboard', end: true, icon: 'M3 12h4v8H3zM10 4h4v16h-4zM17 9h4v11h-4z' },
  { to: '/org/orders', label: 'Orders', icon: 'M4 4h16v4H4zM4 10h16v10H4zm4 3h8' },
  { to: '/org/products', label: 'Catalog', icon: 'M4 7l8-4 8 4-8 4zM4 7v10l8 4 8-4V7' },
  { to: '/org/customers', label: 'Customers', icon: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 20a8 8 0 0116 0' },
];

const ADMIN_LINKS = [
  { to: '/org/staff', label: 'Accounts', icon: 'M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z' },
];

export default function OrgLayout() {
  const { user } = useAuth();
  const links = user?.role === 'admin' ? [...LINKS, ...ADMIN_LINKS] : LINKS;

  return (
    <div className="org">
      <aside className="org__rail">
        <div className="org__brand">
          <span className="org__brand-mark">Ops</span>
          <span className="org__brand-sub">Operations console</span>
        </div>

        <nav className="org__nav">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d={link.icon} fill="none" stroke="currentColor" strokeWidth="1.7" />
              </svg>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="org__who">
          <p className="org__who-name">{user?.username}</p>
          <p className="org__who-role">
            {user?.role === 'admin' ? 'Organization admin' : 'Organization staff'}
            {user?.department ? ` · ${user.department}` : ''}
          </p>
          <NavLink to="/" className="org__exit">
            ← Back to the shop
          </NavLink>
        </div>
      </aside>

      <div className="org__content">
        <Outlet />
      </div>
    </div>
  );
}
