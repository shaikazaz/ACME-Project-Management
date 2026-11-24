import { request } from './apiClient.js';

const path = (id) => `/deliverables/${encodeURIComponent(id)}`;
const milestonesPath = (projectId) => `/projects/${encodeURIComponent(projectId)}/milestones`;

/**
 * Searches deliverables.
 * @param {Object} params Search text, filters, sorting and paging.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array, total: number}>} One page of deliverables.
 */
export function listDeliverables(params, signal) {
  return request('/deliverables', { params, signal });
}

/**
 * Loads one deliverable.
 * @param {string|number} id The deliverable.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The deliverable.
 */
export function getDeliverable(id, signal) {
  return request(path(id), { signal });
}

/**
 * Loads the choices for forms and filters.
 * @param {string|number} [projectId] The project a form is for.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} Statuses, priorities, projects, owners, milestones.
 */
export function getDeliverableOptions(projectId, signal) {
  return request('/deliverables/options', { params: { project_id: projectId }, signal });
}

/**
 * Creates a deliverable.
 * @param {string|number} projectId The project.
 * @param {Object} values The deliverable fields.
 * @returns {Promise<Object>} The new deliverable.
 */
export function createDeliverable(projectId, values) {
  return request(`/projects/${encodeURIComponent(projectId)}/deliverables`, {
    method: 'POST', body: values,
  });
}

/**
 * Updates every field of a deliverable.
 * @param {string|number} id The deliverable.
 * @param {Object} values The deliverable fields.
 * @returns {Promise<Object>} The saved deliverable.
 */
export function updateDeliverable(id, values) {
  return request(path(id), { method: 'PUT', body: values });
}

/**
 * Updates the status, progress and actual effort of a deliverable.
 * @param {string|number} id The deliverable.
 * @param {Object} values The progress fields.
 * @returns {Promise<Object>} The saved deliverable.
 */
export function updateProgress(id, values) {
  return request(`${path(id)}/progress`, { method: 'PATCH', body: values });
}

/**
 * Deletes a deliverable.
 * @param {string|number} id The deliverable.
 * @returns {Promise<null>} Nothing.
 */
export function deleteDeliverable(id) {
  return request(path(id), { method: 'DELETE' });
}

/**
 * Makes a deliverable wait for another one.
 * @param {string|number} id The deliverable that waits.
 * @param {number} predecessorId The deliverable to complete first.
 * @returns {Promise<Object>} The deliverable that waits.
 */
export function addPredecessor(id, predecessorId) {
  return request(`${path(id)}/predecessors`, {
    method: 'POST', body: { predecessor_id: predecessorId },
  });
}

/**
 * Stops a deliverable from waiting for another one.
 * @param {string|number} id The deliverable that waits.
 * @param {number} predecessorId The deliverable it waits for.
 * @returns {Promise<null>} Nothing.
 */
export function removePredecessor(id, predecessorId) {
  return request(`${path(id)}/predecessors/${predecessorId}`, { method: 'DELETE' });
}

/**
 * Loads a project's dependency chain.
 * @param {string|number} projectId The project.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{nodes: Array, links: Array}>} The chain.
 */
export function getDependencyChain(projectId, signal) {
  return request(`/projects/${encodeURIComponent(projectId)}/dependencies`, { signal });
}

/**
 * Lists a project's milestones.
 * @param {string|number} projectId The project.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array}>} The milestones.
 */
export function listMilestones(projectId, signal) {
  return request(milestonesPath(projectId), { signal });
}

/**
 * Creates or updates a milestone.
 * @param {string|number} projectId The project.
 * @param {Object} values The milestone fields.
 * @param {number} [id] The milestone to update; omit to create one.
 * @returns {Promise<Object>} The saved milestone.
 */
export function saveMilestone(projectId, values, id) {
  const base = milestonesPath(projectId);
  return id === undefined
    ? request(base, { method: 'POST', body: values })
    : request(`${base}/${id}`, { method: 'PUT', body: values });
}

/**
 * Deletes a milestone.
 * @param {string|number} projectId The project.
 * @param {number} id The milestone.
 * @returns {Promise<null>} Nothing.
 */
export function deleteMilestone(projectId, id) {
  return request(`${milestonesPath(projectId)}/${id}`, { method: 'DELETE' });
}
