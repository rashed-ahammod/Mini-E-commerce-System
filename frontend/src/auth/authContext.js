/**
 * The auth context object itself.
 *
 * It lives apart from the provider so each file exports only one kind of
 * thing (a component, a hook, or a context). React's fast refresh during
 * development relies on that split, and the eslint rule enforces it.
 */

import { createContext } from 'react';

export const AuthContext = createContext(null);
