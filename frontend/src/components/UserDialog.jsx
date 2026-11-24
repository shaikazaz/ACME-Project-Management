import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import useForm from '../hooks/useForm.js';
import { ROLES, validateUser } from '../utils/userForm.js';
import { FormDialog } from './FormLayout.jsx';
import SelectField from './SelectField.jsx';

/**
 * Form to create or edit an account.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function UserDialog({
  user = null, isSelf = false, onCancel, onSubmit,
}) {
  const isNew = user === null;
  const form = useForm(
    {
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
      role: user?.role ?? 'team_member',
      is_active: user?.is_active ?? true,
      ...(isNew && { password: '' }),
    },
    (values) => validateUser(values, isNew),
    (values) => onSubmit({
      ...values, full_name: values.full_name.trim(), email: values.email.trim(),
    }),
  );
  const { field, values } = form;

  return (
    <FormDialog
      title={isNew ? 'New account' : 'Edit account'}
      form={form}
      submitLabel="Save account"
      onCancel={onCancel}
    >
      <TextField required {...field('full_name', 'Full name')} />
      <TextField required type="email" autoComplete="off" {...field('email', 'Email')} />
      <SelectField
        required
        options={ROLES}
        {...field('role', 'Role', {
          disabled: isSelf,
          help: isSelf ? 'You cannot change your own role' : 'A new role signs the person out',
        })}
      />
      {isNew && (
        <TextField
          required
          type="password"
          autoComplete="new-password"
          {...field('password', 'Password', { help: 'At least 12 characters' })}
        />
      )}
      <FormControlLabel
        label="Active: may sign in"
        control={(
          <Switch
            checked={values.is_active}
            disabled={form.busy || isSelf}
            onChange={(event) => form.change('is_active', event.target.checked)}
          />
        )}
      />
    </FormDialog>
  );
}

UserDialog.propTypes = {
  user: PropTypes.shape({
    full_name: PropTypes.string,
    email: PropTypes.string,
    role: PropTypes.string,
    is_active: PropTypes.bool,
  }),
  isSelf: PropTypes.bool,
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

export default UserDialog;
