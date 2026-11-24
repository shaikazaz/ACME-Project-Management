import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import {
  deleteMilestone, listMilestones, saveMilestone,
} from '../services/deliverableService.js';
import { formatDate } from '../utils/format.js';
import ConfirmDialog from './ConfirmDialog.jsx';
import MilestoneDialog from './MilestoneDialog.jsx';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';

/**
 * A project's milestones.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The section.
 */
function MilestoneSection({ projectId, canEdit }) {
  const notify = useNotify();
  // editing: undefined when closed, null for a new milestone.
  const [editing, setEditing] = useState(undefined);
  const [deleting, setDeleting] = useState(null);
  const { data, error, reload } = useLoad(useCallback(
    (signal) => listMilestones(projectId, signal),
    [projectId],
  ));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading milestones" />;

  const handleSave = async (values) => {
    await saveMilestone(projectId, values, editing?.id);
    setEditing(undefined);
    notify('Milestone saved');
    reload();
  };
  const handleDelete = async () => {
    await deleteMilestone(projectId, deleting.id);
    setDeleting(null);
    notify('Milestone deleted');
    reload();
  };

  return (
    <>
      {canEdit && (
        <Button variant="contained" sx={{ mb: 2 }} onClick={() => setEditing(null)}>
          New milestone
        </Button>
      )}
      {data.items.length === 0 && (
        <EmptyState title="No milestones yet" text="Milestones mark the key dates of a project." />
      )}
      <Box sx={{ display: 'grid', gap: 2 }}>
        {data.items.map((item) => (
          <Paper key={item.id} sx={{ p: 2, overflowWrap: 'anywhere' }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              <Typography variant="h6" component="h2">{item.name}</Typography>
              {item.completed_date && (
                <Chip
                  size="small"
                  color="success"
                  label={`Completed ${formatDate(item.completed_date)}`}
                />
              )}
              {item.is_overdue && (
                <Chip size="small" color="error" variant="outlined" label="Overdue" />
              )}
            </Box>
            <Typography variant="body2">
              {`Due ${formatDate(item.due_date)} · ${item.completed_count} of `
                + `${item.deliverable_count} deliverables completed`}
            </Typography>
            {item.description && <Typography>{item.description}</Typography>}
            {canEdit && (
              <Box sx={{ mt: 1 }}>
                <Button
                  size="small"
                  onClick={() => setEditing(item)}
                  aria-label={`Edit ${item.name}`}
                >
                  Edit
                </Button>
                <Button
                  size="small"
                  color="error"
                  onClick={() => setDeleting(item)}
                  aria-label={`Delete ${item.name}`}
                >
                  Delete
                </Button>
              </Box>
            )}
          </Paper>
        ))}
      </Box>
      {editing !== undefined && (
        <MilestoneDialog
          milestone={editing}
          onCancel={() => setEditing(undefined)}
          onSubmit={handleSave}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this milestone?"
          text={`${deleting.name} will be deleted. Its deliverables are kept.`}
          confirmLabel="Delete milestone"
          onCancel={() => setDeleting(null)}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

MilestoneSection.propTypes = {
  projectId: PropTypes.number.isRequired,
  canEdit: PropTypes.bool.isRequired,
};

export default MilestoneSection;
