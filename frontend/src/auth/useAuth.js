/**
 * Read the auth state from anywhere in the tree.
 *
 * Kept in its own file so that AuthContext.jsx only exports components and
 * this only exports a hook, which keeps react-refresh (and its eslint rule)
 * happy during development.
 */

import { useContext } from 'react';

import { AuthContext } from './authContext';

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used inside an <AuthProvider>.');
  }
  return context;
}
