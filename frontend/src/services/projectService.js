import { request } from './apiClient.js';

/**
 * Searches projects.
 * @param {Object} params Search text, filters, sorting and paging.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array, total: number}>} One page of projects.
 */
export function listProjects(params, signal) {
  return request('/projects', { params, signal });
}

/**
 * Loads one project.
 * @param {string|number} id The project.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The project.
 */
export function getProject(id, signal) {
  return request(`/projects/${encodeURIComponent(id)}`, { signal });
}

/**
 * Loads the choices for forms and filters.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} Statuses, priorities, departments and managers.
 */
export function getProjectOptions(signal) {
  return request('/projects/options', { signal });
}

/**
 * Creates or updates a project.
 * @param {Object} values The project fields.
 * @param {string|number} [id] The project to update; omit to create one.
 * @returns {Promise<Object>} The saved project.
 */
export function saveProject(values, id) {
  return id === undefined
    ? request('/projects', { method: 'POST', body: values })
    : request(`/projects/${encodeURIComponent(id)}`, { method: 'PUT', body: values });
}

/**
 * Deletes a project.
 * @param {string|number} id The project.
 * @param {string} confirmCode The code the user typed to confirm.
 * @returns {Promise<null>} Nothing.
 */
export function deleteProject(id, confirmCode) {
  return request(`/projects/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    params: { confirm_code: confirmCode },
  });
}

/**
 * Creates a department.
 * @param {string} name The department name.
 * @returns {Promise<Object>} The new department.
 */
export function createDepartment(name) {
  return request('/departments', { method: 'POST', body: { name } });
}
