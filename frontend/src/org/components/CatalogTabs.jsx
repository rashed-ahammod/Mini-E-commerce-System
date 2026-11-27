/** Switch between the two halves of catalog management. */

import { NavLink } from 'react-router-dom';

export default function CatalogTabs() {
  return (
    <nav className="tabs" aria-label="Catalog sections">
      <NavLink to="/org/products" className={({ isActive }) => (isActive ? 'is-active' : '')}>
        Products
      </NavLink>
      <NavLink to="/org/categories" className={({ isActive }) => (isActive ? 'is-active' : '')}>
        Categories
      </NavLink>
    </nav>
  );
}
