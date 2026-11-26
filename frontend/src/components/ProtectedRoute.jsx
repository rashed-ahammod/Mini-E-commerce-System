/**
 * Wraps routes that need a logged-in user (checkout, order history).
 *
 * While the startup token check runs we show a short message rather than
 * redirecting, otherwise refreshing a protected page would always bounce a
 * logged-in user to the login screen.
 *
 * The current location is passed along so the login page can send the user
 * back where they were heading.
 */

import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <p className="status">Checking your session…</p>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
