import PropTypes from 'prop-types';
import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import { readTokens, setSessionEndedHandler } from '../services/apiClient.js';
import * as authService from '../services/authService.js';
import { AuthContext, useNotify } from './contexts.js';

/**
 * Keeps track of who is signed in, including after a page refresh.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The provider.
 */
function AuthProvider({ children }) {
  const notify = useNotify();
  // status: loading, signedIn, signedOut or failed (server unreachable).
  const [auth, setAuth] = useState(() => ({
    status: readTokens() ? 'loading' : 'signedOut',
    user: null,
  }));

  useEffect(() => {
    setSessionEndedHandler(() => {
      setAuth((current) => {
        if (current.status === 'signedIn') {
          notify('Your session has ended. Please sign in again.', 'warning');
        }
        return { status: 'signedOut', user: null };
      });
    });
    return () => setSessionEndedHandler(() => {});
  }, [notify]);

  useEffect(() => {
    if (auth.status !== 'loading') return undefined;
    const controller = new AbortController();
    authService.getCurrentUser(controller.signal).then(
      (user) => setAuth({ status: 'signedIn', user }),
      (error) => {
        if (controller.signal.aborted || error.status === 401) return;
        setAuth({ status: 'failed', user: null });
      },
    );
    return () => controller.abort();
  }, [auth.status]);

  const login = useCallback(async (email, password) => {
    const user = await authService.login(email, password);
    setAuth({ status: 'signedIn', user });
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      notify('Signed out here, but the server could not be reached.', 'warning');
    }
    setAuth({ status: 'signedOut', user: null });
  }, [notify]);

  const value = useMemo(() => ({
    ...auth,
    login,
    logout,
    updateUser: (changes) => setAuth((current) => ({
      ...current, user: { ...current.user, ...changes },
    })),
    retry: () => setAuth({ status: 'loading', user: null }),
    can: (permission) => auth.user?.permissions.includes(permission) ?? false,
  }), [auth, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = { children: PropTypes.node.isRequired };

export default AuthProvider;
