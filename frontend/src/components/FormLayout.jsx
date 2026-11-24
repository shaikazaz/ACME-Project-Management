import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Paper from '@mui/material/Paper';
import PropTypes from 'prop-types';

const formPropTypes = {
  form: PropTypes.shape({
    formError: PropTypes.string,
    busy: PropTypes.bool,
    handleSubmit: PropTypes.func,
  }).isRequired,
  submitLabel: PropTypes.string.isRequired,
  onCancel: PropTypes.func.isRequired,
  children: PropTypes.node.isRequired,
};

/**
 * The frame of a full-page form.
 * @param {Object} props Component props; form comes from useForm.
 * @returns {JSX.Element} The form.
 */
export function FormPage({
  form, submitLabel, onCancel, children,
}) {
  return (
    <Paper component="form" noValidate onSubmit={form.handleSubmit} sx={{ p: 3 }}>
      {form.formError && <Alert severity="error" sx={{ mb: 2 }}>{form.formError}</Alert>}
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: {
            xs: 'minmax(0, 1fr)',
            md: 'repeat(2, minmax(0, 1fr))',
          },
          alignItems: 'start',
        }}
      >
        {children}
      </Box>
      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 3 }}>
        <Button onClick={onCancel} disabled={form.busy}>Cancel</Button>
        <Button type="submit" variant="contained" disabled={form.busy}>{submitLabel}</Button>
      </Box>
    </Paper>
  );
}

FormPage.propTypes = formPropTypes;

/**
 * The frame of a form in a dialog.
 * @param {Object} props Component props; form comes from useForm.
 * @returns {JSX.Element} The dialog.
 */
export function FormDialog({
  title, form, submitLabel, onCancel, children,
}) {
  return (
    <Dialog
      open
      fullWidth
      maxWidth="sm"
      onClose={form.busy ? undefined : onCancel}
      aria-labelledby="form-title"
    >
      <form noValidate onSubmit={form.handleSubmit}>
        <DialogTitle id="form-title">{title}</DialogTitle>
        <DialogContent>
          {form.formError && <Alert severity="error" sx={{ mb: 2 }}>{form.formError}</Alert>}
          <Box sx={{ display: 'grid', gap: 2, pt: 1 }}>{children}</Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onCancel} disabled={form.busy}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={form.busy}>{submitLabel}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

FormDialog.propTypes = { ...formPropTypes, title: PropTypes.string.isRequired };
