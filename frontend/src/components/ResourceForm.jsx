import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import useDepartments from '../hooks/useDepartments.js';
import useForm from '../hooks/useForm.js';
import { toRequest, validateResource } from '../utils/resourceForm.js';
import DepartmentField from './DepartmentField.jsx';
import { FormPage } from './FormLayout.jsx';
import NewDepartmentDialog from './NewDepartmentDialog.jsx';
import SelectField from './SelectField.jsx';

/**
 * Form to create or edit a resource.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The form.
 */
function ResourceForm({
  initialValues, options, submitLabel, onSubmit, onCancel,
}) {
  const form = useForm(
    initialValues,
    validateResource,
    (values) => onSubmit(toRequest(values)),
  );
  const list = useDepartments(options.departments);
  const { field } = form;

  return (
    <>
      <FormPage form={form} submitLabel={submitLabel} onCancel={onCancel}>
        <TextField required {...field('employee_code', 'Employee code')} />
        <TextField required {...field('full_name', 'Full name')} />
        <TextField required type="email" {...field('email', 'Email')} />
        <TextField required {...field('job_title', 'Job title')} />
        <DepartmentField
          departments={list.departments}
          field={field('department_id', 'Department')}
          onAdd={list.open}
        />
        <TextField {...field('skills', 'Skills', { help: 'Separate skills with commas' })} />
        <TextField
          required
          slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          {...field('capacity_percent', 'Capacity (%)', { help: '100 is full time' })}
        />
        <SelectField
          required
          options={options.availability}
          {...field('availability', 'Availability')}
        />
        <SelectField
          options={options.users}
          emptyLabel="No account"
          {...field('user_id', 'Sign-in account', {
            help: 'Lets this person see their assigned work',
          })}
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

ResourceForm.propTypes = {
  initialValues: PropTypes.shape({ employee_code: PropTypes.string }).isRequired,
  options: PropTypes.shape({
    departments: PropTypes.arrayOf(PropTypes.object),
    availability: PropTypes.arrayOf(PropTypes.string),
    users: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
  submitLabel: PropTypes.string.isRequired,
  onSubmit: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

export default ResourceForm;
