import { publicRequest, request, storeTokens } from './apiClient.js';

/**
 * Signs in and stores the tokens.
 * @param {string} email The email.
 * @param {string} password The password.
 * @returns {Promise<Object>} The signed-in user.
 */
export async function login(email, password) {
  const result = await publicRequest('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
  storeTokens({ access: result.access_token, refresh: result.refresh_token });
  return result.user;
}

/**
 * Signs out on the server, then clears the tokens here.
 * @returns {Promise<void>} Settles when done.
 */
export async function logout() {
  try {
    await request('/auth/logout', { method: 'POST' });
  } finally {
    storeTokens(null);
  }
}

/**
 * Loads the signed-in user.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The user.
 */
export function getCurrentUser(signal) {
  return request('/auth/me', { signal });
}

/**
 * Changes the signed-in user's password. Other devices are signed out.
 * @param {string} currentPassword The current password.
 * @param {string} newPassword The new password.
 * @returns {Promise<void>} Settles when done.
 */
export async function changePassword(currentPassword, newPassword) {
  const result = await request('/auth/change-password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  });
  storeTokens({ access: result.access_token, refresh: result.refresh_token });
}
