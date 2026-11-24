import { request } from './apiClient.js';

/**
 * Loads the dashboard of the projects the user manages.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The dashboard.
 */
export default function getDashboard(signal) {
  return request('/dashboard', { signal });
}
