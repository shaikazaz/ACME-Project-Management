import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useState } from 'react';

/**
 * Asks the user to confirm, and shows why a confirmed action failed.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function ConfirmDialog({
  title, text, confirmLabel, onCancel, onConfirm,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const handleConfirm = async () => {
    setBusy(true);
    setError('');
    try {
      await onConfirm();
    } catch (failure) {
      setError(failure.message);
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={busy ? undefined : onCancel} aria-labelledby="confirm-title">
      <DialogTitle id="confirm-title">{title}</DialogTitle>
      <DialogContent>
        <Typography sx={{ overflowWrap: 'anywhere' }}>{text}</Typography>
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={busy}>Cancel</Button>
        <Button color="error" variant="contained" onClick={handleConfirm} disabled={busy}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ConfirmDialog.propTypes = {
  title: PropTypes.string.isRequired,
  text: PropTypes.string.isRequired,
  confirmLabel: PropTypes.string.isRequired,
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
};

export default ConfirmDialog;
