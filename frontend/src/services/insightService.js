import { request } from './apiClient.js';

/**
 * Generates insights from a project's latest data. Saves nothing.
 * @param {number} projectId The project.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The insights, their source and the verified metrics.
 */
export default function generateInsights(projectId, signal) {
  return request(`/projects/${encodeURIComponent(projectId)}/insights`, {
    method: 'POST', signal,
  });
}
