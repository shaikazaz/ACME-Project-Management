import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import { useState } from 'react';
import { createDepartment } from '../services/projectService.js';

/**
 * Lets an admin add a department while filling in a project.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function NewDepartmentDialog({ onCancel, onCreated }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    try {
      onCreated(await createDepartment(name.trim()));
    } catch (failure) {
      setError(failure.message);
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={busy ? undefined : onCancel} aria-labelledby="department-title">
      <form onSubmit={handleSubmit}>
        <DialogTitle id="department-title">New department</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            margin="normal"
            label="Department name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={Boolean(error)}
            helperText={error}
            disabled={busy}
            slotProps={{ htmlInput: { maxLength: 120 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={!name.trim() || busy}>
            Add department
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

NewDepartmentDialog.propTypes = {
  onCancel: PropTypes.func.isRequired,
  onCreated: PropTypes.func.isRequired,
};

export default NewDepartmentDialog;
