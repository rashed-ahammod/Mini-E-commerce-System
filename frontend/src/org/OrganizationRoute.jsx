/**
 * Gate for the organization area.
 *
 * The role comes from the login response, so the UI knows what kind of
 * account it is holding without probing an endpoint and reading a 403.
 *
 * A customer who reaches one of these URLs is sent to the shop rather than
 * to the login page: they are signed in perfectly well, just not as someone
 * who runs the shop, and asking them to log in again would be misleading.
 */

import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export default function OrganizationRoute({ children, adminOnly = false }) {
  const { user, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <p className="status">Checking your session…</p>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user.is_organization) {
    return <Navigate to="/" replace />;
  }

  // Managing colleagues is an admin job; staff get the rest of the area.
  if (adminOnly && user.role !== 'admin') {
    return <Navigate to="/org" replace />;
  }

  return children;
}
