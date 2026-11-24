import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import PropTypes from 'prop-types';
import { useAuth } from '../context/contexts.js';
import SelectField from './SelectField.jsx';

/**
 * A department list that lets admins add a department. The dialog belongs
 * outside the form, because forms cannot be nested.
 * @param {Object} props Component props; field comes from useForm.
 * @returns {JSX.Element} The field.
 */
function DepartmentField({ departments, field, onAdd }) {
  const { can } = useAuth();
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', sm: 'row' },
        gap: 1,
        alignItems: 'start',
      }}
    >
      <SelectField required options={departments} {...field} />
      {can('departments:manage') && (
        <Button sx={{ whiteSpace: 'nowrap' }} onClick={onAdd} disabled={field.disabled}>
          New department
        </Button>
      )}
    </Box>
  );
}

DepartmentField.propTypes = {
  departments: PropTypes.arrayOf(PropTypes.object).isRequired,
  field: PropTypes.shape({ disabled: PropTypes.bool }).isRequired,
  onAdd: PropTypes.func.isRequired,
};

export default DepartmentField;
