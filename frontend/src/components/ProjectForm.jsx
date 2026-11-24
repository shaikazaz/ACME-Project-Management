import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import { useAuth } from '../context/contexts.js';
import useDepartments from '../hooks/useDepartments.js';
import useForm from '../hooks/useForm.js';
import { today } from '../utils/format.js';
import { toRequest, validateProject } from '../utils/projectForm.js';
import DateField from './DateField.jsx';
import DepartmentField from './DepartmentField.jsx';
import { FormPage } from './FormLayout.jsx';
import NewDepartmentDialog from './NewDepartmentDialog.jsx';
import SelectField from './SelectField.jsx';

/**
 * Form to create or edit a project.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The form.
 */
function ProjectForm({
  initialValues, options, submitLabel, onSubmit, onCancel,
}) {
  const { can } = useAuth();
  const isAdmin = can('projects:create');
  const form = useForm(
    initialValues,
    (values) => validateProject(values, today()),
    (values) => onSubmit(toRequest(values)),
  );
  const list = useDepartments(options.departments);
  const { field, values } = form;
  const adminField = (name, label, help = '') => field(name, label, {
    help: isAdmin ? help : 'Only an admin can change this',
    disabled: !isAdmin,
  });

  return (
    <>
      <FormPage form={form} submitLabel={submitLabel} onCancel={onCancel}>
        <TextField
          required
          {...adminField('code', 'Project code', 'For example CRM-2026')}
        />
        <TextField required {...field('name', 'Project name')} />
        <TextField
          multiline
          minRows={3}
          sx={{ gridColumn: '1 / -1' }}
          {...field('description', 'Description')}
        />
        <DepartmentField
          departments={list.departments}
          field={adminField('department_id', 'Department')}
          onAdd={list.open}
        />
        <SelectField
          options={options.managers}
          emptyLabel="No manager yet"
          {...adminField('manager_id', 'Project manager')}
        />
        <DateField required {...field('start_date', 'Start date')} />
        <DateField required {...field('end_date', 'End date')} />
        <SelectField required options={options.statuses} {...field('status', 'Status')} />
        <SelectField
          required
          options={options.priorities}
          {...field('priority', 'Priority')}
        />
        {values.status === 'Completed' && (
          <DateField required {...field('actual_completion_date', 'Completion date')} />
        )}
        <TextField
          required
          slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          {...field('planned_budget', 'Planned budget (USD)')}
        />
      </FormPage>
      {list.adding && (
        <NewDepartmentDialog
          onCancel={list.close}
          onCreated={(department) => {
            list.add(department);
            form.change('department_id', department.id);
          }}
        />
      )}
    </>
  );
}

ProjectForm.propTypes = {
  initialValues: PropTypes.shape({ status: PropTypes.string }).isRequired,
  options: PropTypes.shape({
    statuses: PropTypes.arrayOf(PropTypes.string),
    priorities: PropTypes.arrayOf(PropTypes.string),
    departments: PropTypes.arrayOf(PropTypes.object),
    managers: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
  submitLabel: PropTypes.string.isRequired,
  onSubmit: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

export default ProjectForm;
