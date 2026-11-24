import { request } from './apiClient.js';

const path = (id) => `/resources/${encodeURIComponent(id)}`;
const assignmentsPath = (projectId) => `/projects/${encodeURIComponent(projectId)}/assignments`;

/**
 * Searches resources.
 * @param {Object} params Search text, filters, period, sorting and paging.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array, total: number}>} One page of resources.
 */
export function listResources(params, signal) {
  return request('/resources', { params, signal });
}

/**
 * Loads one resource with its assignments and workload.
 * @param {string|number} id The resource.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The resource.
 */
export function getResource(id, signal) {
  return request(path(id), { signal });
}

/**
 * Loads the choices for forms and filters.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} Availability, departments, skills and accounts.
 */
export function getResourceOptions(signal) {
  return request('/resources/options', { signal });
}

/**
 * Loads the workload report.
 * @param {Object} params The period.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The report.
 */
export function getWorkloadReport(params, signal) {
  return request('/resources/workload', { params, signal });
}

/**
 * Creates or updates a resource.
 * @param {Object} values The resource fields.
 * @param {string|number} [id] The resource to update; omit to create one.
 * @returns {Promise<Object>} The saved resource.
 */
export function saveResource(values, id) {
  return id === undefined
    ? request('/resources', { method: 'POST', body: values })
    : request(path(id), { method: 'PUT', body: values });
}

/**
 * Deletes a resource.
 * @param {string|number} id The resource.
 * @returns {Promise<null>} Nothing.
 */
export function deleteResource(id) {
  return request(path(id), { method: 'DELETE' });
}

/**
 * Lists a project's assignments.
 * @param {string|number} projectId The project.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array}>} The assignments.
 */
export function listAssignments(projectId, signal) {
  return request(assignmentsPath(projectId), { signal });
}

/**
 * Creates or updates an assignment.
 * @param {string|number} projectId The project.
 * @param {Object} values The assignment fields.
 * @param {number} [id] The assignment to update; omit to create one.
 * @returns {Promise<Object>} The saved assignment with the person's workload.
 */
export function saveAssignment(projectId, values, id) {
  const base = assignmentsPath(projectId);
  return id === undefined
    ? request(base, { method: 'POST', body: values })
    : request(`${base}/${id}`, { method: 'PUT', body: values });
}

/**
 * Removes a person from a project.
 * @param {string|number} projectId The project.
 * @param {number} id The assignment.
 * @returns {Promise<null>} Nothing.
 */
export function deleteAssignment(projectId, id) {
  return request(`${assignmentsPath(projectId)}/${id}`, { method: 'DELETE' });
}
