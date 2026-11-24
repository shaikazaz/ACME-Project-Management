import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import useForm from '../hooks/useForm.js';
import { today } from '../utils/format.js';
import DateField from './DateField.jsx';
import { FormDialog } from './FormLayout.jsx';

function validate(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = 'Enter a name';
  if (!values.due_date) errors.due_date = 'Choose a due date';
  if (values.completed_date > today()) {
    errors.completed_date = 'Completion date cannot be in the future';
  }
  return errors;
}

/**
 * Form to create or edit a milestone.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function MilestoneDialog({ milestone = null, onCancel, onSubmit }) {
  const form = useForm(
    {
      name: milestone?.name ?? '',
      description: milestone?.description ?? '',
      due_date: milestone?.due_date ?? '',
      completed_date: milestone?.completed_date ?? '',
    },
    validate,
    (values) => onSubmit({
      ...values, name: values.name.trim(), completed_date: values.completed_date || null,
    }),
  );
  const { field } = form;
  return (
    <FormDialog
      title={milestone ? 'Edit milestone' : 'New milestone'}
      form={form}
      submitLabel="Save milestone"
      onCancel={onCancel}
    >
      <TextField
        required
        slotProps={{ htmlInput: { maxLength: 200 } }}
        {...field('name', 'Milestone name')}
      />
      <TextField multiline minRows={2} {...field('description', 'Description')} />
      <DateField required {...field('due_date', 'Due date')} />
      <DateField
        {...field('completed_date', 'Completed on', { help: 'Leave empty until it is reached' })}
      />
    </FormDialog>
  );
}

MilestoneDialog.propTypes = {
  milestone: PropTypes.shape({
    name: PropTypes.string,
    description: PropTypes.string,
    due_date: PropTypes.string,
    completed_date: PropTypes.string,
  }),
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

export default MilestoneDialog;
