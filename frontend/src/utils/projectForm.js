export const EMPTY_PROJECT = {
  code: '',
  name: '',
  description: '',
  department_id: '',
  manager_id: '',
  start_date: '',
  end_date: '',
  actual_completion_date: '',
  status: 'Planned',
  priority: 'Medium',
  planned_budget: '0',
};

/**
 * Converts a project from the API into form values.
 * @param {Object} project The project.
 * @returns {Object} The form values.
 */
export function toFormValues(project) {
  return {
    ...Object.fromEntries(
      Object.keys(EMPTY_PROJECT).map((name) => [name, project[name] ?? '']),
    ),
    department_id: project.department.id,
    manager_id: project.manager?.id ?? '',
  };
}

/**
 * Converts form values into an API request.
 * @param {Object} values The form values.
 * @returns {Object} The request body.
 */
export function toRequest(values) {
  return {
    ...values,
    code: values.code.trim(),
    name: values.name.trim(),
    manager_id: values.manager_id || null,
    planned_budget: String(values.planned_budget).trim(),
    actual_completion_date:
      values.status === 'Completed' ? values.actual_completion_date : null,
  };
}

/**
 * Checks form values before they are sent. The server checks them again.
 * @param {Object} values The form values.
 * @param {string} latestDate The latest allowed completion date.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateProject(values, latestDate) {
  const errors = {};
  const code = values.code.trim();
  const completed = values.actual_completion_date;
  if (!code) errors.code = 'Enter a project code';
  else if (!/^[A-Za-z0-9][A-Za-z0-9-]{0,29}$/.test(code)) {
    errors.code = 'Use up to 30 letters, digits and hyphens';
  }
  if (!values.name.trim()) errors.name = 'Enter a project name';
  else if (values.name.trim().length > 200) errors.name = 'Use up to 200 characters';
  if (values.description.length > 5000) errors.description = 'Use up to 5000 characters';
  if (!values.department_id) errors.department_id = 'Choose a department';
  if (!values.start_date) errors.start_date = 'Choose a start date';
  if (!values.end_date) errors.end_date = 'Choose an end date';
  else if (values.start_date && values.end_date < values.start_date) {
    errors.end_date = 'End date must not be before the start date';
  }
  if (!/^\d{1,12}(\.\d{1,2})?$/.test(String(values.planned_budget).trim())) {
    errors.planned_budget = 'Enter an amount such as 25000 or 25000.50';
  }
  if (values.status === 'Completed') {
    if (!completed) errors.actual_completion_date = 'Choose the completion date';
    else if (completed > latestDate) {
      errors.actual_completion_date = 'Completion date cannot be in the future';
    } else if (completed < values.start_date) {
      errors.actual_completion_date = 'Completion date must not be before the start date';
    }
  }
  return errors;
}
