export const EMPTY_DELIVERABLE = {
  name: '',
  description: '',
  milestone_id: '',
  owner_id: '',
  start_date: '',
  due_date: '',
  completion_date: '',
  status: 'Not Started',
  priority: 'Medium',
  progress_percent: '0',
  estimated_hours: '0',
  actual_hours: '0',
};

const PROGRESS_FIELDS = ['status', 'progress_percent', 'actual_hours', 'completion_date'];

/**
 * Converts a deliverable from the API into form values.
 * @param {Object} deliverable The deliverable.
 * @returns {Object} The form values.
 */
export function toFormValues(deliverable) {
  return {
    ...Object.fromEntries(
      Object.keys(EMPTY_DELIVERABLE).map((name) => [name, deliverable[name] ?? '']),
    ),
    milestone_id: deliverable.milestone?.id ?? '',
    owner_id: deliverable.owner?.id ?? '',
  };
}

/**
 * Converts form values into the progress part of an API request.
 * @param {Object} values The form values.
 * @returns {Object} The request body.
 */
export function toProgressRequest(values) {
  const { status } = values;
  const progress = { Completed: '100', 'Not Started': '0' };
  return {
    status,
    progress_percent: progress[status] ?? String(values.progress_percent).trim(),
    actual_hours: String(values.actual_hours).trim(),
    completion_date: status === 'Completed' ? values.completion_date || null : null,
  };
}

/**
 * Converts form values into a full API request.
 * @param {Object} values The form values.
 * @returns {Object} The request body.
 */
export function toRequest(values) {
  return {
    ...values,
    ...toProgressRequest(values),
    name: values.name.trim(),
    milestone_id: values.milestone_id || null,
    owner_id: values.owner_id || null,
    estimated_hours: String(values.estimated_hours).trim(),
  };
}

function checkHours(value) {
  return /^\d{1,6}(\.\d{1,2})?$/.test(String(value).trim())
    ? undefined
    : 'Enter hours such as 8 or 7.5';
}

function clean(errors) {
  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message));
}

/**
 * Checks the progress fields. The server checks them again.
 * @param {Object} values The form values.
 * @param {string} latestDate The latest allowed completion date.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateProgress(values, latestDate) {
  const progress = String(values.progress_percent).trim();
  const editable = ['In Progress', 'Blocked'].includes(values.status);
  const validPercent = /^\d{1,2}(\.\d{1,2})?$/.test(progress);
  return clean({
    progress_percent: editable && !validPercent
      ? 'Enter a percentage below 100, or set the status to Completed'
      : undefined,
    actual_hours: checkHours(values.actual_hours),
    completion_date: values.status === 'Completed' && values.completion_date > latestDate
      ? 'Completion date cannot be in the future'
      : undefined,
  });
}

/**
 * Checks every deliverable field. The server checks them again.
 * @param {Object} values The form values.
 * @param {string} latestDate The latest allowed completion date.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateDeliverable(values, latestDate) {
  const name = values.name.trim();
  const { start_date: start, due_date: due } = values;
  const nameProblem = name.length > 200 ? 'Use up to 200 characters' : undefined;
  const dueProblem = start && due < start
    ? 'Due date must not be before the start date'
    : undefined;
  return {
    ...validateProgress(values, latestDate),
    ...clean({
      name: name ? nameProblem : 'Enter a name',
      description: values.description.length > 5000 ? 'Use up to 5000 characters' : undefined,
      start_date: start ? undefined : 'Choose a start date',
      due_date: due ? dueProblem : 'Choose a due date',
      estimated_hours: checkHours(values.estimated_hours),
    }),
  };
}

/**
 * Picks the fields that the progress dialog edits.
 * @param {Object} deliverable The deliverable.
 * @returns {Object} The form values.
 */
export function toProgressValues(deliverable) {
  const values = toFormValues(deliverable);
  return Object.fromEntries(PROGRESS_FIELDS.map((name) => [name, values[name]]));
}

/**
 * Explains what a deliverable is waiting for.
 * @param {Object[]} blockedBy The unfinished predecessors.
 * @returns {string} The explanation, or an empty string.
 */
export function describeBlockers(blockedBy) {
  if (blockedBy.length === 0) return '';
  return `Waiting for ${blockedBy.map(({ name }) => name).join(', ')}`;
}
