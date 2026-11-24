export const ROLES = [
  { id: 'admin', name: 'Admin' },
  { id: 'project_manager', name: 'Project Manager' },
  { id: 'team_member', name: 'Team Member' },
];

/**
 * Names a role.
 * @param {string} role The role.
 * @returns {string} The name.
 */
export function roleName(role) {
  return ROLES.find(({ id }) => id === role)?.name ?? role;
}

/**
 * Checks a new password. The server checks it again.
 * @param {string} password The password.
 * @returns {string|undefined} The problem, if any.
 */
export function checkPassword(password) {
  if (password.length < 12) return 'Use at least 12 characters';
  if (password.length > 128) return 'Use up to 128 characters';
  return new Set(password).size < 4 ? 'Use at least 4 different characters' : undefined;
}

/**
 * Checks an account before it is sent. The server checks it again.
 * @param {Object} values The form values.
 * @param {boolean} isNew Whether the account needs a password.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateUser(values, isNew) {
  const errors = {};
  if (!values.full_name.trim()) errors.full_name = 'Enter a name';
  else if (values.full_name.trim().length > 120) errors.full_name = 'Use up to 120 characters';
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email.trim())) {
    errors.email = 'Enter a valid email';
  }
  const problem = isNew && checkPassword(values.password);
  if (problem) errors.password = problem;
  return errors;
}

/**
 * Checks a password and its repetition.
 * @param {Object} values new_password and repeat.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateNewPassword(values) {
  const problem = checkPassword(values.new_password);
  if (problem) return { new_password: problem };
  return values.new_password === values.repeat
    ? {}
    : { repeat: 'The passwords do not match' };
}
