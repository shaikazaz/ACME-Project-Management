import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback } from 'react';
import useForm from '../hooks/useForm.js';
import useLoad from '../hooks/useLoad.js';
import { listResources } from '../services/resourceService.js';
import { validateAssignment } from '../utils/resourceForm.js';
import DateField from './DateField.jsx';
import { FormDialog } from './FormLayout.jsx';
import SelectField from './SelectField.jsx';

const MAX_PEOPLE = 100;

/**
 * Form to assign a person to a project, or change an assignment.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function AssignmentDialog({
  project, assignment = null, takenIds, onCancel, onSubmit,
}) {
  const form = useForm(
    {
      resource_id: assignment?.resource.id ?? '',
      project_role: assignment?.project_role ?? '',
      allocation_percent: assignment ? String(assignment.allocation_percent) : '',
      start_date: assignment?.start_date ?? project.start_date,
      end_date: assignment?.end_date ?? project.end_date,
    },
    validateAssignment,
    (values) => onSubmit({
      ...values, allocation_percent: String(values.allocation_percent).trim(),
    }),
  );
  const { field, values } = form;

  // People who can be added: available and not yet in the project.
  const isNew = assignment === null;
  const people = useLoad(useCallback(
    (signal) => (isNew
      ? listResources({ availability: ['Available', 'On Leave'], limit: MAX_PEOPLE }, signal)
      : Promise.resolve({ items: [] })),
    [isNew],
  ));
  const choices = (people.data?.items ?? []).filter(({ id }) => !takenIds.includes(id));
  const chosen = choices.find(({ id }) => id === values.resource_id);
  const options = isNew
    ? choices.map(({ id, full_name: name, workload }) => ({
      id, name: `${name} (${workload.peak_percent}% of ${workload.capacity_percent}%)`,
    }))
    : [assignment.resource];

  return (
    <FormDialog
      title={isNew ? 'Assign a person' : 'Change assignment'}
      form={form}
      submitLabel="Save assignment"
      onCancel={onCancel}
    >
      <SelectField
        required
        options={options}
        {...field('resource_id', 'Person', {
          disabled: !isNew || people.loading,
          help: people.error?.message ?? 'Shows the peak load and capacity',
        })}
      />
      {chosen && (
        <Typography variant="body2">
          {`Free at the peak: ${Math.max(0, chosen.workload.remaining_percent)}%`}
        </Typography>
      )}
      <TextField
        slotProps={{ htmlInput: { maxLength: 120 } }}
        {...field('project_role', 'Role in the project')}
      />
      <TextField
        required
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
        {...field('allocation_percent', 'Allocation (%)', { help: 'Of a full-time week' })}
      />
      <DateField required {...field('start_date', 'Start date')} />
      <DateField required {...field('end_date', 'End date')} />
    </FormDialog>
  );
}

AssignmentDialog.propTypes = {
  project: PropTypes.shape({
    start_date: PropTypes.string.isRequired,
    end_date: PropTypes.string.isRequired,
  }).isRequired,
  assignment: PropTypes.shape({
    resource: PropTypes.shape({ id: PropTypes.number }),
    project_role: PropTypes.string,
    allocation_percent: PropTypes.number,
    start_date: PropTypes.string,
    end_date: PropTypes.string,
  }),
  takenIds: PropTypes.arrayOf(PropTypes.number).isRequired,
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

export default AssignmentDialog;
