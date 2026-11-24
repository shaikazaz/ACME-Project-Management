import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import DeliverableStatus from '../components/DeliverableStatus.jsx';
import DependencyEditor from '../components/DependencyEditor.jsx';
import { Fact, FactList } from '../components/Facts.jsx';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import ProgressDialog from '../components/ProgressDialog.jsx';
import { PriorityChip, ProgressBar } from '../components/ProjectChips.jsx';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import {
  deleteDeliverable, getDeliverable, updateProgress,
} from '../services/deliverableService.js';
import { describeBlockers } from '../utils/deliverableForm.js';
import { formatDate } from '../utils/format.js';

/**
 * One deliverable in full.
 * @returns {JSX.Element} The page.
 */
function DeliverableDetailsPage() {
  const { deliverableId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const [dialog, setDialog] = useState('');
  const { data: item, error, reload } = useLoad(
    useCallback((signal) => getDeliverable(deliverableId, signal), [deliverableId]),
  );

  if (error) {
    return error.status === 404
      ? <ErrorState message="This deliverable does not exist, or you may not view it." />
      : <ErrorState message={error.message} onRetry={reload} />;
  }
  // Never show one deliverable while another one is loading.
  if (String(item?.id) !== deliverableId) return <LoadingState label="Loading deliverable" />;

  const projectLink = `/projects/${item.project.id}?tab=deliverables`;
  const handleProgress = async (values) => {
    await updateProgress(item.id, values);
    setDialog('');
    notify('Progress saved');
    reload();
  };
  const handleDelete = async () => {
    await deleteDeliverable(item.id);
    notify(`Deleted ${item.name}`);
    navigate(projectLink, { replace: true });
  };

  return (
    <>
      <Button component={Link} to={projectLink}>{`Back to ${item.project.name}`}</Button>
      <Box
        sx={{
          display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'space-between', my: 1,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline">{item.project.code}</Typography>
          <Typography variant="h4" component="h1" sx={{ overflowWrap: 'anywhere' }}>
            {item.name}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
          {item.can_update && (
            <Button variant="contained" onClick={() => setDialog('progress')}>
              Update progress
            </Button>
          )}
          {item.can_edit && (
            <>
              <Button component={Link} to={`/deliverables/${item.id}/edit`}>Edit</Button>
              <Button color="error" onClick={() => setDialog('delete')}>Delete</Button>
            </>
          )}
        </Box>
      </Box>
      {item.blocked_by.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {`Blocked. ${describeBlockers(item.blocked_by)}.`}
        </Alert>
      )}
      <Paper sx={{ p: 3 }}>
        <FactList>
          <Fact label="Status"><DeliverableStatus deliverable={item} /></Fact>
          <Fact label="Priority"><PriorityChip priority={item.priority} /></Fact>
          <Fact label="Progress"><ProgressBar value={item.progress_percent} /></Fact>
          <Fact label="Owner">{item.owner?.name ?? 'Not assigned'}</Fact>
          <Fact label="Milestone">{item.milestone?.name ?? '—'}</Fact>
          <Fact label="Effort (actual / estimated)">
            {`${item.actual_hours} / ${item.estimated_hours} hours`}
          </Fact>
          <Fact label="Start date">{formatDate(item.start_date)}</Fact>
          <Fact label="Due date">{formatDate(item.due_date)}</Fact>
          <Fact label="Completed on">{formatDate(item.completion_date)}</Fact>
        </FactList>
        <Typography variant="h6" component="h2" sx={{ mt: 3 }}>Description</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
          {item.description || 'No description.'}
        </Typography>
      </Paper>
      <DependencyEditor key={item.id} deliverable={item} onChanged={reload} />
      {dialog === 'progress' && (
        <ProgressDialog
          deliverable={item}
          onCancel={() => setDialog('')}
          onSubmit={handleProgress}
        />
      )}
      {dialog === 'delete' && (
        <ConfirmDialog
          title="Delete this deliverable?"
          text={`${item.name} will be permanently deleted.`}
          confirmLabel="Delete deliverable"
          onCancel={() => setDialog('')}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

export default DeliverableDetailsPage;
