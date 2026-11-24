import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useState } from 'react';

/**
 * Asks the user to type the project code before deleting.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function DeleteProjectDialog({ project, onCancel, onConfirm }) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const matches = code.trim().toUpperCase() === project.code.toUpperCase();

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!matches || busy) return;
    setBusy(true);
    setError('');
    try {
      await onConfirm(code.trim());
    } catch (failure) {
      setError(failure.message);
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={busy ? undefined : onCancel} aria-labelledby="delete-title">
      <form onSubmit={handleSubmit}>
        <DialogTitle id="delete-title">Delete this project?</DialogTitle>
        <DialogContent>
          <Typography>
            {`This permanently deletes ${project.name} with its `
              + `${project.deliverable_count} deliverables, `
              + `${project.milestone_count} milestones and `
              + `${project.assignment_count} assignments.`}
          </Typography>
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          <TextField
            autoFocus
            fullWidth
            margin="normal"
            label={`Type ${project.code} to confirm`}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            disabled={busy}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button type="submit" color="error" variant="contained" disabled={!matches || busy}>
            Delete project
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

DeleteProjectDialog.propTypes = {
  project: PropTypes.shape({
    code: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    deliverable_count: PropTypes.number.isRequired,
    milestone_count: PropTypes.number.isRequired,
    assignment_count: PropTypes.number.isRequired,
  }).isRequired,
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
};

export default DeleteProjectDialog;
