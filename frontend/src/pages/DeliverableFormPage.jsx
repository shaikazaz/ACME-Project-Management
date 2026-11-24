import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import DeliverableForm from '../components/DeliverableForm.jsx';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import {
  createDeliverable, getDeliverable, getDeliverableOptions, updateDeliverable,
} from '../services/deliverableService.js';
import { getProject } from '../services/projectService.js';
import { EMPTY_DELIVERABLE, toFormValues } from '../utils/deliverableForm.js';

/**
 * Page to create a deliverable, or edit the one named in the address.
 * @returns {JSX.Element} The page.
 */
function DeliverableFormPage() {
  const { projectId, deliverableId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data, error, reload } = useLoad(useCallback(async (signal) => {
    const deliverable = deliverableId ? await getDeliverable(deliverableId, signal) : null;
    const id = deliverable?.project.id ?? projectId;
    const [project, options] = await Promise.all([
      getProject(id, signal), getDeliverableOptions(id, signal),
    ]);
    return { deliverable, project, options };
  }, [projectId, deliverableId]));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading form" />;
  const { deliverable, project, options } = data;
  if (!project.can_edit) {
    return <ErrorState message="You do not have permission to edit this project's work." />;
  }

  const handleSubmit = async (values) => {
    const saved = deliverable
      ? await updateDeliverable(deliverable.id, values)
      : await createDeliverable(project.id, values);
    notify(deliverable ? 'Deliverable updated' : 'Deliverable created');
    navigate(`/deliverables/${saved.id}`, { replace: true });
  };

  return (
    <>
      <Typography variant="overline">{project.name}</Typography>
      <Typography variant="h4" component="h1" gutterBottom>
        {deliverable ? 'Edit deliverable' : 'New deliverable'}
      </Typography>
      <DeliverableForm
        initialValues={deliverable ? toFormValues(deliverable) : EMPTY_DELIVERABLE}
        options={options}
        submitLabel={deliverable ? 'Save changes' : 'Create deliverable'}
        onSubmit={handleSubmit}
        onCancel={() => navigate(deliverable
          ? `/deliverables/${deliverable.id}`
          : `/projects/${project.id}?tab=deliverables`)}
      />
    </>
  );
}

export default DeliverableFormPage;
