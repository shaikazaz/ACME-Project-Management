import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useCallback, useState } from 'react';
import {
  Link, useNavigate, useParams, useSearchParams,
} from 'react-router-dom';
import AiInsights from '../components/AiInsights.jsx';
import BudgetAlert from '../components/BudgetAlert.jsx';
import DeleteProjectDialog from '../components/DeleteProjectDialog.jsx';
import DependencyChain from '../components/DependencyChain.jsx';
import MilestoneSection from '../components/MilestoneSection.jsx';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import ProjectBudget from '../components/ProjectBudget.jsx';
import ProjectDeliverables from '../components/ProjectDeliverables.jsx';
import ProjectOverview from '../components/ProjectOverview.jsx';
import ProjectTeam from '../components/ProjectTeam.jsx';
import RiskPanel from '../components/RiskPanel.jsx';
import { useAuth, useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import { deleteProject, getProject } from '../services/projectService.js';

const CLOSED = ['Completed', 'Cancelled'];

/**
 * One project in full.
 * @returns {JSX.Element} The page.
 */
function ProjectDetailsPage() {
  const { projectId } = useParams();
  const { can } = useAuth();
  const navigate = useNavigate();
  const notify = useNotify();
  const [params, setParams] = useSearchParams();
  const [deleting, setDeleting] = useState(false);
  const { data: project, error, reload } = useLoad(
    useCallback((signal) => getProject(projectId, signal), [projectId]),
  );

  if (error) {
    return error.status === 404
      ? <ErrorState message="This project does not exist, or you may not view it." />
      : <ErrorState message={error.message} onRetry={reload} />;
  }
  // Never show one project while another one is loading.
  if (String(project?.id) !== projectId) return <LoadingState label="Loading project" />;

  const canEditWork = project.can_edit && !CLOSED.includes(project.status);
  const tabs = {
    overview: ['Overview', <ProjectOverview key="o" project={project} />],
    deliverables: [
      'Deliverables',
      <ProjectDeliverables key="d" project={project} canEdit={canEditWork} />,
    ],
    milestones: [
      'Milestones',
      <MilestoneSection key="m" projectId={project.id} canEdit={canEditWork} />,
    ],
    ...(can('resources:view') && {
      team: ['Team', <ProjectTeam key="t" project={project} canEdit={canEditWork} />],
    }),
    ...(project.can_edit && {
      budget: ['Budget', <ProjectBudget key="b" projectId={project.id} />],
      dependencies: [
        'Dependencies',
        <DependencyChain key="c" projectId={project.id} projectCode={project.code} />,
      ],
      insights: ['AI Insights', <AiInsights key={project.id} projectId={project.id} />],
    }),
  };
  const tab = params.get('tab') in tabs ? params.get('tab') : 'overview';

  const handleDelete = async (code) => {
    await deleteProject(project.id, code);
    notify(`Deleted ${project.name}`);
    navigate('/projects', { replace: true });
  };

  return (
    <>
      <Button component={Link} to="/projects">Back to projects</Button>
      <Box
        sx={{
          display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'space-between', my: 1,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline">{project.code}</Typography>
          <Typography variant="h4" component="h1" sx={{ overflowWrap: 'anywhere' }}>
            {project.name}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {project.can_edit && (
            <Button variant="contained" component={Link} to={`/projects/${project.id}/edit`}>
              Edit
            </Button>
          )}
          {project.can_delete && (
            <Button color="error" onClick={() => setDeleting(true)}>Delete</Button>
          )}
        </Box>
      </Box>
      {tab === 'overview' && project.risk && <RiskPanel risk={project.risk} />}
      {tab === 'overview' && !project.risk && project.budget && (
        <BudgetAlert budget={project.budget} />
      )}
      <Tabs
        value={tab}
        onChange={(_, next) => setParams({ tab: next }, { replace: true })}
        variant="scrollable"
        aria-label="Project sections"
        sx={{ mb: 2 }}
      >
        {Object.entries(tabs).map(([key, [label]]) => (
          <Tab key={key} value={key} label={label} id={`tab-${key}`} aria-controls="tab-panel" />
        ))}
      </Tabs>
      <Box role="tabpanel" id="tab-panel" aria-labelledby={`tab-${tab}`}>{tabs[tab][1]}</Box>
      {tab === 'overview' && can('projects:delete') && !project.can_delete && (
        <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary' }}>
          Only planned or cancelled projects can be deleted.
        </Typography>
      )}
      {deleting && (
        <DeleteProjectDialog
          project={project}
          onCancel={() => setDeleting(false)}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

export default ProjectDetailsPage;
