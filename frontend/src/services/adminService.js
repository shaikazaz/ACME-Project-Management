import { request } from './apiClient.js';

const userPath = (id) => `/users/${encodeURIComponent(id)}`;

/**
 * Searches accounts.
 * @param {Object} params Search text, filters and paging.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array, total: number}>} One page of accounts.
 */
export function listUsers(params, signal) {
  return request('/users', { params, signal });
}

/**
 * Creates or updates an account.
 * @param {Object} values The account fields.
 * @param {number} [id] The account to update; omit to create one.
 * @returns {Promise<Object>} The saved account.
 */
export function saveUser(values, id) {
  return id === undefined
    ? request('/users', { method: 'POST', body: values })
    : request(userPath(id), { method: 'PUT', body: values });
}

/**
 * Sets an account's password and signs the person out.
 * @param {number} id The account.
 * @param {string} password The new password.
 * @returns {Promise<null>} Nothing.
 */
export function resetPassword(id, password) {
  return request(`${userPath(id)}/reset-password`, {
    method: 'POST', body: { new_password: password },
  });
}

/**
 * Deletes an account.
 * @param {number} id The account.
 * @returns {Promise<null>} Nothing.
 */
export function deleteUser(id) {
  return request(userPath(id), { method: 'DELETE' });
}

/**
 * Lists departments.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array}>} The departments.
 */
export function listDepartments(signal) {
  return request('/departments', { signal });
}

/**
 * Creates or updates a department.
 * @param {Object} values The department fields.
 * @param {number} [id] The department to update; omit to create one.
 * @returns {Promise<Object>} The saved department.
 */
export function saveDepartment(values, id) {
  return id === undefined
    ? request('/departments', { method: 'POST', body: values })
    : request(`/departments/${id}`, { method: 'PUT', body: values });
}

/**
 * Deletes a department.
 * @param {number} id The department.
 * @returns {Promise<null>} Nothing.
 */
export function deleteDepartment(id) {
  return request(`/departments/${id}`, { method: 'DELETE' });
}

/**
 * Lists the application settings.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array}>} The settings.
 */
export function listSettings(signal) {
  return request('/settings', { signal });
}

/**
 * Changes a setting.
 * @param {string} key The setting.
 * @param {string} value The new value.
 * @returns {Promise<Object>} The setting.
 */
export function saveSetting(key, value) {
  return request(`/settings/${encodeURIComponent(key)}`, { method: 'PUT', body: { value } });
}
