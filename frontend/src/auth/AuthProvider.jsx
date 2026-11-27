/**
 * Who is logged in, for the whole app.
 *
 * The flow:
 * - on startup, if a token is in localStorage, ask /auth/me/ whether it is
 *   still valid (it would not be after a logout elsewhere, or a database
 *   reset during development);
 * - login and register store the token and the user;
 * - logout tells the backend to destroy the token, then clears it locally
 *   even if that call fails.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import { getToken, setToken } from '../api/client';
import { authApi } from '../api/endpoints';
import { AuthContext } from './authContext';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // `loading` is true only during the startup check, so protected routes can
  // wait instead of bouncing a logged-in user to the login page on refresh.
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;

    let cancelled = false;

    authApi
      .me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        // Any failure here means the stored token is no longer usable.
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (credentials) => {
    const { token, user: loggedIn } = await authApi.login(credentials);
    setToken(token);
    setUser(loggedIn);
    return loggedIn;
  }, []);

  const register = useCallback(async (details) => {
    // Registering returns a token too, so a new account is logged in at once.
    const { token, user: created } = await authApi.register(details);
    setToken(token);
    setUser(created);
    return created;
  }, []);

  /**
   * Re-read the account from the server.
   *
   * The profile page calls this after saving, so the details the rest of the
   * app reads off `user` — the address checkout prefills, and whether the
   * profile is complete — are the ones that were just stored, rather than a
   * copy that drifts the moment anything changes.
   */
  const refreshUser = useCallback(async () => {
    const me = await authApi.me();
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // The token may already be invalid server-side; either way the user
      // asked to log out, so clear it locally regardless.
    }
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      // Everything an order needs before it can be delivered. The shop uses
      // this to prompt for what is missing instead of failing at checkout.
      profileComplete: Boolean(user?.profile_complete),
      missingDetails: user?.missing_details ?? [],
      login,
      register,
      logout,
      refreshUser,
    }),
    [user, loading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
