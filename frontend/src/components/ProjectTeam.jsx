import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import {
  deleteAssignment, listAssignments, saveAssignment,
} from '../services/resourceService.js';
import { formatDate } from '../utils/format.js';
import AssignmentDialog from './AssignmentDialog.jsx';
import AvailabilityChip from './AvailabilityChip.jsx';
import ConfirmDialog from './ConfirmDialog.jsx';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';
import WorkloadBar from './WorkloadBar.jsx';

/**
 * The people assigned to a project.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The section.
 */
function ProjectTeam({ project, canEdit }) {
  const notify = useNotify();
  // editing: undefined when closed, null for a new assignment.
  const [editing, setEditing] = useState(undefined);
  const [removing, setRemoving] = useState(null);
  const { data, error, reload } = useLoad(useCallback(
    (signal) => listAssignments(project.id, signal),
    [project.id],
  ));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading team" />;

  const handleSave = async (values) => {
    const saved = await saveAssignment(project.id, values, editing?.id);
    setEditing(undefined);
    const { peak_percent: peak, capacity_percent: capacity } = saved.workload;
    if (saved.workload.is_over_allocated) {
      notify(
        `${saved.resource.name} is over-allocated: ${peak}% of ${capacity}% capacity.`,
        'warning',
      );
    } else {
      notify('Assignment saved');
    }
    reload();
  };
  const handleRemove = async () => {
    await deleteAssignment(project.id, removing.id);
    setRemoving(null);
    notify('Assignment removed');
    reload();
  };

  return (
    <>
      {canEdit && (
        <Button variant="contained" sx={{ mb: 2 }} onClick={() => setEditing(null)}>
          Assign a person
        </Button>
      )}
      {data.items.length === 0 && (
        <EmptyState title="Nobody is assigned yet" text="Assigned people appear here." />
      )}
      <Box sx={{ display: 'grid', gap: 2 }}>
        {data.items.map((item) => (
          <Paper key={item.id} sx={{ p: 2, overflowWrap: 'anywhere' }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              <MuiLink component={Link} to={`/resources/${item.resource.id}`}>
                {item.resource.name}
              </MuiLink>
              <AvailabilityChip availability={item.availability} />
            </Box>
            <Typography variant="body2" sx={{ my: 1 }}>
              {`${item.project_role || item.job_title} · ${item.allocation_percent}% `
                + `(${item.allocation_hours} h per week) · `
                + `${formatDate(item.start_date)} to ${formatDate(item.end_date)}`}
            </Typography>
            <Typography variant="caption">Peak load across all projects</Typography>
            <WorkloadBar workload={item.workload} />
            {canEdit && (
              <Box sx={{ mt: 1 }}>
                <Button
                  size="small"
                  onClick={() => setEditing(item)}
                  aria-label={`Change ${item.resource.name}`}
                >
                  Change
                </Button>
                <Button
                  size="small"
                  color="error"
                  onClick={() => setRemoving(item)}
                  aria-label={`Remove ${item.resource.name}`}
                >
                  Remove
                </Button>
              </Box>
            )}
          </Paper>
        ))}
      </Box>
      {editing !== undefined && (
        <AssignmentDialog
          project={project}
          assignment={editing}
          takenIds={data.items.map(({ resource }) => resource.id)}
          onCancel={() => setEditing(undefined)}
          onSubmit={handleSave}
        />
      )}
      {removing && (
        <ConfirmDialog
          title="Remove this person?"
          text={`${removing.resource.name} will no longer be assigned to this project.`}
          confirmLabel="Remove person"
          onCancel={() => setRemoving(null)}
          onConfirm={handleRemove}
        />
      )}
    </>
  );
}

ProjectTeam.propTypes = {
  project: PropTypes.shape({
    id: PropTypes.number.isRequired,
    start_date: PropTypes.string.isRequired,
    end_date: PropTypes.string.isRequired,
  }).isRequired,
  canEdit: PropTypes.bool.isRequired,
};

export default ProjectTeam;
