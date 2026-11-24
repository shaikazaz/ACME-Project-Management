export const EMPTY_RESOURCE = {
  employee_code: '',
  full_name: '',
  email: '',
  department_id: '',
  job_title: '',
  skills: '',
  capacity_percent: '100',
  availability: 'Available',
  user_id: '',
};

const PERCENT = /^\d{1,3}(\.\d{1,2})?$/;

/**
 * Converts a resource from the API into form values.
 * @param {Object} resource The resource.
 * @returns {Object} The form values.
 */
export function toFormValues(resource) {
  return {
    employee_code: resource.employee_code,
    full_name: resource.full_name,
    email: resource.email,
    department_id: resource.department.id,
    job_title: resource.job_title,
    skills: resource.skills.join(', '),
    capacity_percent: String(resource.workload.capacity_percent),
    availability: resource.availability,
    user_id: resource.user?.id ?? '',
  };
}

function splitSkills(text) {
  return text.split(',').map((skill) => skill.trim()).filter(Boolean);
}

/**
 * Converts form values into an API request.
 * @param {Object} values The form values.
 * @returns {Object} The request body.
 */
export function toRequest(values) {
  return {
    ...values,
    skills: splitSkills(values.skills),
    capacity_percent: String(values.capacity_percent).trim(),
    user_id: values.user_id || null,
  };
}

/**
 * Checks a resource before it is sent. The server checks it again.
 * @param {Object} values The form values.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateResource(values) {
  const errors = {};
  const capacity = String(values.capacity_percent).trim();
  const skills = splitSkills(values.skills);
  if (!/^[A-Za-z0-9][A-Za-z0-9-]{0,29}$/.test(values.employee_code.trim())) {
    errors.employee_code = 'Use up to 30 letters, digits and hyphens';
  }
  if (!values.full_name.trim()) errors.full_name = 'Enter a name';
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email.trim())) {
    errors.email = 'Enter a valid email';
  }
  if (!values.department_id) errors.department_id = 'Choose a department';
  if (!values.job_title.trim()) errors.job_title = 'Enter a job title';
  if (skills.length > 20 || skills.some((skill) => skill.length > 50)) {
    errors.skills = 'Use up to 20 skills of 50 characters';
  }
  if (!PERCENT.test(capacity) || Number(capacity) > 100) {
    errors.capacity_percent = 'Enter a percentage from 0 to 100';
  }
  return errors;
}

/**
 * Checks an assignment before it is sent. The server checks it again.
 * @param {Object} values The form values.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateAssignment(values) {
  const errors = {};
  const percent = String(values.allocation_percent).trim();
  if (!values.resource_id) errors.resource_id = 'Choose a person';
  if (!PERCENT.test(percent) || Number(percent) <= 0 || Number(percent) > 100) {
    errors.allocation_percent = 'Enter a percentage above 0, up to 100';
  }
  if (!values.start_date) errors.start_date = 'Choose a start date';
  if (!values.end_date) errors.end_date = 'Choose an end date';
  else if (values.start_date && values.end_date < values.start_date) {
    errors.end_date = 'End date must not be before the start date';
  }
  return errors;
}
