import { createContext, useContext } from 'react';

export const AuthContext = createContext(null);
export const NotificationContext = createContext(() => {});

/**
 * Gives access to the signed-in user and sign-in actions.
 * @returns {Object} user, status, login, logout, updateUser, retry and can.
 */
export function useAuth() {
  return useContext(AuthContext);
}

/**
 * Gives access to notifications.
 * @returns {function(string, string=): void} Shows a message with a severity.
 */
export function useNotify() {
  return useContext(NotificationContext);
}
