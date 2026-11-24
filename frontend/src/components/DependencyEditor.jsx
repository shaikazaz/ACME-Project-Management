import Alert from '@mui/material/Alert';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';
import useLoad from '../hooks/useLoad.js';
import {
  addPredecessor, listDeliverables, removePredecessor,
} from '../services/deliverableService.js';
import RelatedDeliverable from './RelatedDeliverable.jsx';

function Related({
  title, items, emptyText, projectCode, onRemove = null, busy = false,
}) {
  return (
    <>
      <Typography variant="h6" component="h2">{title}</Typography>
      {items.length === 0 && (
        <Typography sx={{ color: 'text.secondary' }}>{emptyText}</Typography>
      )}
      <List aria-label={title} dense>
        {items.map((item, index) => (
          <ListItem key={item.id ?? `hidden-${index}`} disableGutters sx={{ gap: 1 }}>
            <RelatedDeliverable item={item} projectCode={projectCode} />
            {onRemove && item.id !== null && (
              <Button
                size="small"
                color="error"
                disabled={busy}
                onClick={() => onRemove(item)}
                aria-label={`Remove dependency on ${item.name}`}
              >
                Remove
              </Button>
            )}
          </ListItem>
        ))}
      </List>
    </>
  );
}

Related.propTypes = {
  title: PropTypes.string.isRequired,
  items: PropTypes.arrayOf(PropTypes.object).isRequired,
  emptyText: PropTypes.string.isRequired,
  projectCode: PropTypes.string.isRequired,
  onRemove: PropTypes.func,
  busy: PropTypes.bool,
};

/**
 * Shows a deliverable's dependencies, and lets managers change them.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The editor.
 */
function DependencyEditor({ deliverable, onChanged }) {
  const [text, setText] = useState('');
  const [choice, setChoice] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const canEdit = deliverable.can_edit;

  // Managers search all the work they can see, including other projects.
  const search = choice ? '' : text;
  const found = useLoad(useCallback(
    (signal) => (canEdit
      ? listDeliverables({ search, sort: 'name', limit: 50 }, signal)
      : Promise.resolve({ items: [] })),
    [canEdit, search],
  ));
  const taken = new Set([deliverable.id, ...deliverable.predecessors.map(({ id }) => id)]);
  const options = (found.data?.items ?? []).filter(({ id }) => !taken.has(id));

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
      setChoice(null);
      setText('');
      onChanged();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper component="section" aria-label="Dependencies" sx={{ p: 3, mt: 2 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Related
        title="Must be completed first"
        items={deliverable.predecessors}
        emptyText="This deliverable does not wait for anything."
        projectCode={deliverable.project.code}
        busy={busy}
        onRemove={canEdit
          ? (item) => run(() => removePredecessor(deliverable.id, item.id))
          : null}
      />
      {canEdit && (
        <Box sx={{ display: 'flex', gap: 1, mb: 3, alignItems: 'center' }}>
          <Autocomplete
            fullWidth
            size="small"
            options={options}
            value={choice}
            inputValue={text}
            loading={found.loading}
            filterOptions={(all) => all}
            getOptionLabel={(option) => `${option.project.code} · ${option.name}`}
            getOptionKey={(option) => option.id}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            onChange={(_, value) => setChoice(value)}
            onInputChange={(_, value) => setText(value)}
            renderInput={(params) => <TextField {...params} label="Add a predecessor" />}
          />
          <Button
            variant="outlined"
            disabled={!choice || busy}
            onClick={() => run(() => addPredecessor(deliverable.id, choice.id))}
          >
            Add
          </Button>
        </Box>
      )}
      <Related
        title="Waiting for this"
        items={deliverable.successors}
        emptyText="Nothing waits for this deliverable."
        projectCode={deliverable.project.code}
      />
    </Paper>
  );
}

DependencyEditor.propTypes = {
  deliverable: PropTypes.shape({
    id: PropTypes.number.isRequired,
    can_edit: PropTypes.bool.isRequired,
    project: PropTypes.shape({ code: PropTypes.string.isRequired }).isRequired,
    predecessors: PropTypes.arrayOf(PropTypes.object).isRequired,
    successors: PropTypes.arrayOf(PropTypes.object).isRequired,
  }).isRequired,
  onChanged: PropTypes.func.isRequired,
};

export default DependencyEditor;
