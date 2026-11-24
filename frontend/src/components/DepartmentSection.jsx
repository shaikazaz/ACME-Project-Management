import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useState } from 'react';
import { useNotify } from '../context/contexts.js';
import useForm from '../hooks/useForm.js';
import useLoad from '../hooks/useLoad.js';
import {
  deleteDepartment, listDepartments, saveDepartment,
} from '../services/adminService.js';
import ConfirmDialog from './ConfirmDialog.jsx';
import { FormDialog } from './FormLayout.jsx';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';

function validate(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = 'Enter a name';
  if (values.description.length > 2000) errors.description = 'Use up to 2000 characters';
  return errors;
}

function DepartmentDialog({ department = null, onCancel, onSubmit }) {
  const form = useForm(
    { name: department?.name ?? '', description: department?.description ?? '' },
    validate,
    (values) => onSubmit({ ...values, name: values.name.trim() }),
  );
  return (
    <FormDialog
      title={department ? 'Edit department' : 'New department'}
      form={form}
      submitLabel="Save department"
      onCancel={onCancel}
    >
      <TextField
        required
        slotProps={{ htmlInput: { maxLength: 120 } }}
        {...form.field('name', 'Department name')}
      />
      <TextField multiline minRows={2} {...form.field('description', 'Description')} />
    </FormDialog>
  );
}

DepartmentDialog.propTypes = {
  department: PropTypes.shape({ name: PropTypes.string, description: PropTypes.string }),
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

/**
 * Department administration.
 * @returns {JSX.Element} The section.
 */
function DepartmentSection() {
  const notify = useNotify();
  const { data, error, reload } = useLoad(listDepartments);
  // editing: undefined when closed, null for a new department.
  const [editing, setEditing] = useState(undefined);
  const [deleting, setDeleting] = useState(null);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading departments" />;

  const handleSave = async (values) => {
    await saveDepartment(values, editing?.id);
    setEditing(undefined);
    notify('Department saved');
    reload();
  };
  const handleDelete = async () => {
    await deleteDepartment(deleting.id);
    setDeleting(null);
    notify('Department deleted');
    reload();
  };

  return (
    <>
      <Button variant="contained" sx={{ mb: 2 }} onClick={() => setEditing(null)}>
        New department
      </Button>
      {data.items.length === 0 && (
        <EmptyState title="No departments yet" text="Projects and people need a department." />
      )}
      <Box sx={{ display: 'grid', gap: 1 }}>
        {data.items.map((item) => (
          <Paper key={item.id} sx={{ p: 2, overflowWrap: 'anywhere' }}>
            <Typography variant="h6" component="h2">{item.name}</Typography>
            {item.description && <Typography>{item.description}</Typography>}
            <Button
              size="small"
              aria-label={`Edit ${item.name}`}
              onClick={() => setEditing(item)}
            >
              Edit
            </Button>
            <Button
              size="small"
              color="error"
              aria-label={`Delete ${item.name}`}
              onClick={() => setDeleting(item)}
            >
              Delete
            </Button>
          </Paper>
        ))}
      </Box>
      {editing !== undefined && (
        <DepartmentDialog
          department={editing}
          onCancel={() => setEditing(undefined)}
          onSubmit={handleSave}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this department?"
          text={`${deleting.name} will be permanently deleted.`}
          confirmLabel="Delete department"
          onCancel={() => setDeleting(null)}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

export default DepartmentSection;
