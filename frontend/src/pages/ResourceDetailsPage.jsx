import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import AvailabilityChip from '../components/AvailabilityChip.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import { Fact, FactList } from '../components/Facts.jsx';
import { EmptyState, ErrorState, LoadingState } from '../components/PageStates.jsx';
import WorkloadBar from '../components/WorkloadBar.jsx';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import { deleteResource, getResource } from '../services/resourceService.js';
import { formatDate } from '../utils/format.js';

const span = (item) => `${formatDate(item.start_date)} to ${formatDate(item.end_date)}`;

/**
 * One resource with assignments and workload over time.
 * @returns {JSX.Element} The page.
 */
function ResourceDetailsPage() {
  const { resourceId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const [deleting, setDeleting] = useState(false);
  const { data: item, error, reload } = useLoad(
    useCallback((signal) => getResource(resourceId, signal), [resourceId]),
  );

  if (error) {
    return error.status === 404
      ? <ErrorState message="This resource does not exist." />
      : <ErrorState message={error.message} onRetry={reload} />;
  }
  if (String(item?.id) !== resourceId) return <LoadingState label="Loading resource" />;

  const { workload } = item;
  const handleDelete = async () => {
    await deleteResource(item.id);
    notify(`Deleted ${item.full_name}`);
    navigate('/resources', { replace: true });
  };

  return (
    <>
      <Button component={Link} to="/resources">Back to resources</Button>
      <Box
        sx={{
          display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'space-between', my: 1,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline">{item.employee_code}</Typography>
          <Typography variant="h4" component="h1" sx={{ overflowWrap: 'anywhere' }}>
            {item.full_name}
          </Typography>
        </Box>
        {item.can_edit && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Button variant="contained" component={Link} to={`/resources/${item.id}/edit`}>
              Edit
            </Button>
            <Button color="error" onClick={() => setDeleting(true)}>Delete</Button>
          </Box>
        )}
      </Box>
      {workload.is_over_allocated && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {`Over-allocated: up to ${workload.peak_percent}% is assigned, but the capacity `
            + `is ${workload.capacity_percent}%.`}
        </Alert>
      )}
      <Paper sx={{ p: 3 }}>
        <FactList>
          <Fact label="Job title">{item.job_title}</Fact>
          <Fact label="Department">{item.department.name}</Fact>
          <Fact label="Availability">
            <AvailabilityChip
              availability={item.availability}
              needsCover={item.needs_cover}
            />
          </Fact>
          <Fact label="Email">{item.email}</Fact>
          <Fact label="Sign-in account">{item.user?.name ?? 'None'}</Fact>
          <Fact label="Skills">{item.skills.join(', ') || '—'}</Fact>
          <Fact label="Capacity">
            {`${workload.capacity_percent}% (${workload.capacity_hours} h per week)`}
          </Fact>
          <Fact label="Allocated today">
            {`${workload.current_percent}% (${workload.current_hours} h per week)`}
          </Fact>
          <Fact label="Peak load"><WorkloadBar workload={workload} /></Fact>
          <Fact label="Utilization at the peak">
            {workload.utilization_percent === null
              ? 'No capacity'
              : `${workload.utilization_percent}%`}
          </Fact>
          <Fact label="Left at the peak">{`${workload.remaining_percent}%`}</Fact>
        </FactList>
      </Paper>
      <Typography variant="h6" component="h2" sx={{ mt: 3 }}>Assignments</Typography>
      {item.assignments.length === 0 && (
        <EmptyState title="No assignments" text="Assign this person from a project's team." />
      )}
      <Box sx={{ display: 'grid', gap: 1 }}>
        {item.assignments.map((row, index) => (
          <Paper key={row.project_id ?? `hidden-${index}`} sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              {row.project_id === null
                ? <Typography component="span">{row.project_name}</Typography>
                : (
                  <MuiLink component={Link} to={`/projects/${row.project_id}?tab=team`}>
                    {`${row.project_code} · ${row.project_name}`}
                  </MuiLink>
                )}
              {!row.counts && (
                <Chip size="small" label={`${row.project_status}: not counted`} />
              )}
            </Box>
            <Typography variant="body2">
              {`${row.allocation_percent}% · ${span(row)}`
                + `${row.project_role ? ` · ${row.project_role}` : ''}`}
            </Typography>
          </Paper>
        ))}
      </Box>
      <Typography variant="h6" component="h2" sx={{ mt: 3 }}>Load from today</Typography>
      {item.periods.length === 0 && (
        <Typography sx={{ color: 'text.secondary' }}>Nothing is allocated.</Typography>
      )}
      <Box component="ul" aria-label="Load from today" sx={{ m: 0, pl: 3 }}>
        {item.periods.map((row) => (
          <Typography
            component="li"
            key={row.start_date}
            sx={{ color: row.is_over_allocated ? 'error.main' : 'text.primary' }}
          >
            {`${span(row)}: ${row.total_percent}%`
              + `${row.is_over_allocated ? ' (over capacity)' : ''}`}
          </Typography>
        ))}
      </Box>
      {deleting && (
        <ConfirmDialog
          title="Delete this resource?"
          text={`${item.full_name} will be permanently deleted.`}
          confirmLabel="Delete resource"
          onCancel={() => setDeleting(false)}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

export default ResourceDetailsPage;
