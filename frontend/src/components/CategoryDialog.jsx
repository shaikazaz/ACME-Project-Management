import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useState } from 'react';
import useLoad from '../hooks/useLoad.js';
import { deleteCategory, listCategories, saveCategory } from '../services/budgetService.js';

/**
 * Lets an admin manage expense categories.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function CategoryDialog({ onClose }) {
  const { data, error, reload } = useLoad(listCategories);
  const [name, setName] = useState('');
  const [renaming, setRenaming] = useState(null);
  const [problem, setProblem] = useState('');
  const [busy, setBusy] = useState(false);

  const run = async (action) => {
    setBusy(true);
    setProblem('');
    try {
      await action();
      setName('');
      setRenaming(null);
      reload();
    } catch (failure) {
      setProblem(failure.message);
    } finally {
      setBusy(false);
    }
  };
  const handleSubmit = (event) => {
    event.preventDefault();
    if (name.trim() && !busy) run(() => saveCategory(name.trim(), renaming?.id));
  };

  return (
    <Dialog open fullWidth maxWidth="sm" onClose={onClose} aria-labelledby="category-title">
      <DialogTitle id="category-title">Expense categories</DialogTitle>
      <DialogContent>
        {(problem || error) && (
          <Alert severity="error" sx={{ mb: 2 }}>{problem || error.message}</Alert>
        )}
        <Box component="ul" aria-label="Categories" sx={{ p: 0, listStyle: 'none' }}>
          {(data?.items ?? []).map((item) => (
            <Box component="li" key={item.id} sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography sx={{ flexGrow: 1, overflowWrap: 'anywhere' }}>
                {`${item.name} (${item.expense_count})`}
              </Typography>
              <Button
                size="small"
                disabled={busy}
                aria-label={`Rename ${item.name}`}
                onClick={() => {
                  setRenaming(item);
                  setName(item.name);
                }}
              >
                Rename
              </Button>
              <Button
                size="small"
                color="error"
                disabled={busy || item.expense_count > 0}
                aria-label={`Delete ${item.name}`}
                onClick={() => run(() => deleteCategory(item.id))}
              >
                Delete
              </Button>
            </Box>
          ))}
        </Box>
        <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', gap: 1, pt: 1 }}>
          <TextField
            size="small"
            fullWidth
            label={renaming ? `New name for ${renaming.name}` : 'New category'}
            value={name}
            onChange={(event) => setName(event.target.value)}
            slotProps={{ htmlInput: { maxLength: 80 } }}
          />
          <Button type="submit" variant="contained" disabled={!name.trim() || busy}>
            {renaming ? 'Rename category' : 'Add category'}
          </Button>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

CategoryDialog.propTypes = { onClose: PropTypes.func.isRequired };

export default CategoryDialog;
