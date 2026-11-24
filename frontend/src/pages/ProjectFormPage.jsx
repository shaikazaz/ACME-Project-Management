import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import ProjectForm from '../components/ProjectForm.jsx';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import { getProject, getProjectOptions, saveProject } from '../services/projectService.js';
import { EMPTY_PROJECT, toFormValues } from '../utils/projectForm.js';

/**
 * Page to create a project, or edit the one named in the address.
 * @returns {JSX.Element} The page.
 */
function ProjectFormPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data, error, reload } = useLoad(useCallback(async (signal) => {
    const [options, project] = await Promise.all([
      getProjectOptions(signal),
      projectId ? getProject(projectId, signal) : null,
    ]);
    return { options, project };
  }, [projectId]));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading form" />;
  if (data.project && !data.project.can_edit) {
    return <ErrorState message="You do not have permission to edit this project." />;
  }

  const handleSubmit = async (values) => {
    const saved = await saveProject(values, projectId);
    notify(projectId ? 'Project updated' : 'Project created');
    navigate(`/projects/${saved.id}`, { replace: true });
  };

  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>
        {projectId ? 'Edit project' : 'New project'}
      </Typography>
      <ProjectForm
        initialValues={data.project ? toFormValues(data.project) : EMPTY_PROJECT}
        options={data.options}
        submitLabel={projectId ? 'Save changes' : 'Create project'}
        onSubmit={handleSubmit}
        onCancel={() => navigate(projectId ? `/projects/${projectId}` : '/projects')}
      />
    </>
  );
}

export default ProjectFormPage;
