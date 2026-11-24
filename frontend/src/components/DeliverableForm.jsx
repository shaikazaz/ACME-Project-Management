import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import useForm from '../hooks/useForm.js';
import { toRequest, validateDeliverable } from '../utils/deliverableForm.js';
import { today } from '../utils/format.js';
import DateField from './DateField.jsx';
import { FormPage } from './FormLayout.jsx';
import ProgressFields from './ProgressFields.jsx';
import SelectField from './SelectField.jsx';

/**
 * Form to create or edit a deliverable.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The form.
 */
function DeliverableForm({
  initialValues, options, submitLabel, onSubmit, onCancel,
}) {
  const form = useForm(
    initialValues,
    (values) => validateDeliverable(values, today()),
    (values) => onSubmit(toRequest(values)),
  );
  const { field } = form;

  return (
    <FormPage form={form} submitLabel={submitLabel} onCancel={onCancel}>
      <TextField required sx={{ gridColumn: '1 / -1' }} {...field('name', 'Name')} />
      <TextField
        multiline
        minRows={3}
        sx={{ gridColumn: '1 / -1' }}
        {...field('description', 'Description')}
      />
      <SelectField
        options={options.owners}
        emptyLabel="No owner yet"
        {...field('owner_id', 'Owner')}
      />
      <SelectField
        options={options.milestones}
        emptyLabel="No milestone"
        {...field('milestone_id', 'Milestone')}
      />
      <DateField required {...field('start_date', 'Start date')} />
      <DateField required {...field('due_date', 'Due date')} />
      <SelectField
        required
        options={options.priorities}
        {...field('priority', 'Priority')}
      />
      <TextField
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
        {...field('estimated_hours', 'Estimated effort (hours)')}
      />
      <ProgressFields form={form} statuses={options.statuses} />
    </FormPage>
  );
}

DeliverableForm.propTypes = {
  initialValues: PropTypes.shape({ status: PropTypes.string }).isRequired,
  options: PropTypes.shape({
    statuses: PropTypes.arrayOf(PropTypes.string),
    priorities: PropTypes.arrayOf(PropTypes.string),
    owners: PropTypes.arrayOf(PropTypes.object),
    milestones: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
  submitLabel: PropTypes.string.isRequired,
  onSubmit: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

export default DeliverableForm;
