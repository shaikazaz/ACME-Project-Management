import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import DateField from './DateField.jsx';
import SelectField from './SelectField.jsx';

/**
 * The status, progress and effort fields of a deliverable.
 * @param {Object} props Component props; form comes from useForm.
 * @returns {JSX.Element} The fields.
 */
function ProgressFields({ form, statuses }) {
  const { field, values } = form;
  const decimal = { htmlInput: { inputMode: 'decimal' } };
  return (
    <>
      <SelectField required options={statuses} {...field('status', 'Status')} />
      {['In Progress', 'Blocked'].includes(values.status) && (
        <TextField
          required
          slotProps={decimal}
          {...field('progress_percent', 'Progress (%)')}
        />
      )}
      {values.status === 'Completed' && (
        <DateField
          {...field('completion_date', 'Completion date', { help: 'Empty means today' })}
        />
      )}
      <TextField slotProps={decimal} {...field('actual_hours', 'Actual effort (hours)')} />
    </>
  );
}

ProgressFields.propTypes = {
  form: PropTypes.shape({
    field: PropTypes.func.isRequired,
    values: PropTypes.shape({ status: PropTypes.string }).isRequired,
  }).isRequired,
  statuses: PropTypes.arrayOf(PropTypes.string).isRequired,
};

export default ProgressFields;
