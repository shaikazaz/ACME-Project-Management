import { request } from './apiClient.js';

const expensePath = (id) => `/expenses/${encodeURIComponent(id)}`;
const projectPath = (id) => `/projects/${encodeURIComponent(id)}`;

/**
 * Searches project budgets.
 * @param {Object} params Search text, filters, sorting and paging.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} One page of budgets, and their totals.
 */
export function listBudgets(params, signal) {
  return request('/budgets', { params, signal });
}

/**
 * Loads a project's budget.
 * @param {string|number} projectId The project.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} The budget with its spending.
 */
export function getProjectBudget(projectId, signal) {
  return request(`${projectPath(projectId)}/budget`, { signal });
}

/**
 * Searches expenses.
 * @param {Object} params Search text, filters, sorting and paging.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} One page of expenses, and the sum of all matches.
 */
export function listExpenses(params, signal) {
  return request('/expenses', { params, signal });
}

/**
 * Loads the choices for forms and filters.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<Object>} Categories and projects.
 */
export function getExpenseOptions(signal) {
  return request('/expenses/options', { signal });
}

/**
 * Adds an expense to a project.
 * @param {string|number} projectId The project.
 * @param {Object} values The expense fields.
 * @returns {Promise<Object>} The expense and the project's new budget.
 */
export function createExpense(projectId, values) {
  return request(`${projectPath(projectId)}/expenses`, { method: 'POST', body: values });
}

/**
 * Updates an expense.
 * @param {number} id The expense.
 * @param {Object} values The expense fields.
 * @returns {Promise<Object>} The expense and the project's new budget.
 */
export function updateExpense(id, values) {
  return request(expensePath(id), { method: 'PUT', body: values });
}

/**
 * Deletes an expense.
 * @param {number} id The expense.
 * @returns {Promise<null>} Nothing.
 */
export function deleteExpense(id) {
  return request(expensePath(id), { method: 'DELETE' });
}

/**
 * Lists expense categories.
 * @param {AbortSignal} [signal] Cancels the request.
 * @returns {Promise<{items: Array}>} The categories.
 */
export function listCategories(signal) {
  return request('/expense-categories', { signal });
}

/**
 * Creates or renames an expense category.
 * @param {string} name The name.
 * @param {number} [id] The category to rename; omit to create one.
 * @returns {Promise<Object>} The category.
 */
export function saveCategory(name, id) {
  return id === undefined
    ? request('/expense-categories', { method: 'POST', body: { name } })
    : request(`/expense-categories/${id}`, { method: 'PUT', body: { name } });
}

/**
 * Deletes an expense category.
 * @param {number} id The category.
 * @returns {Promise<null>} Nothing.
 */
export function deleteCategory(id) {
  return request(`/expense-categories/${id}`, { method: 'DELETE' });
}
