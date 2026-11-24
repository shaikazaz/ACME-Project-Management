import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import ResourceForm from '../components/ResourceForm.jsx';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import { getResource, getResourceOptions, saveResource } from '../services/resourceService.js';
import { EMPTY_RESOURCE, toFormValues } from '../utils/resourceForm.js';

/**
 * Page to create a resource, or edit the one named in the address.
 * @returns {JSX.Element} The page.
 */
function ResourceFormPage() {
  const { resourceId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data, error, reload } = useLoad(useCallback(async (signal) => {
    const [options, resource] = await Promise.all([
      getResourceOptions(signal),
      resourceId ? getResource(resourceId, signal) : null,
    ]);
    // The account already linked to this person stays a choice.
    const users = resource?.user ? [resource.user, ...options.users] : options.users;
    return { options: { ...options, users }, resource };
  }, [resourceId]));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading form" />;

  const handleSubmit = async (values) => {
    const saved = await saveResource(values, resourceId);
    notify(resourceId ? 'Resource updated' : 'Resource created');
    navigate(`/resources/${saved.id}`, { replace: true });
  };

  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>
        {resourceId ? 'Edit resource' : 'New resource'}
      </Typography>
      <ResourceForm
        initialValues={data.resource ? toFormValues(data.resource) : EMPTY_RESOURCE}
        options={data.options}
        submitLabel={resourceId ? 'Save changes' : 'Create resource'}
        onSubmit={handleSubmit}
        onCancel={() => navigate(resourceId ? `/resources/${resourceId}` : '/resources')}
      />
    </>
  );
}

export default ResourceFormPage;
