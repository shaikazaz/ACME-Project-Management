import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import useForm from '../hooks/useForm.js';
import { validateNewPassword } from '../utils/userForm.js';
import { FormDialog } from './FormLayout.jsx';

/**
 * Form to set a password. Changing your own also asks for the current one.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function PasswordDialog({
  title, askCurrent = false, onCancel, onSubmit,
}) {
  const form = useForm(
    { current_password: '', new_password: '', repeat: '' },
    (values) => ({
      ...(askCurrent && !values.current_password
        && { current_password: 'Enter your current password' }),
      ...validateNewPassword(values),
    }),
    onSubmit,
  );
  const { field } = form;
  return (
    <FormDialog title={title} form={form} submitLabel="Save password" onCancel={onCancel}>
      {askCurrent && (
        <TextField
          required
          type="password"
          autoComplete="current-password"
          {...field('current_password', 'Current password')}
        />
      )}
      <TextField
        required
        type="password"
        autoComplete="new-password"
        {...field('new_password', 'New password', { help: 'At least 12 characters' })}
      />
      <TextField
        required
        type="password"
        autoComplete="new-password"
        {...field('repeat', 'Repeat new password')}
      />
    </FormDialog>
  );
}

PasswordDialog.propTypes = {
  title: PropTypes.string.isRequired,
  askCurrent: PropTypes.bool,
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

export default PasswordDialog;
