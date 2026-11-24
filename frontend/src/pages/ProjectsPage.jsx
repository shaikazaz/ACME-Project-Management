import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState } from '../components/PageStates.jsx';
import PagedResults from '../components/PagedResults.jsx';
import ProjectFilters from '../components/ProjectFilters.jsx';
import ProjectList from '../components/ProjectList.jsx';
import { useAuth } from '../context/contexts.js';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import { getProjectOptions, listProjects } from '../services/projectService.js';

const FILTERS = [
  'search', 'status', 'priority', 'department_id', 'manager_id', 'budget_status', 'risk',
  'end_from', 'end_to',
];

/**
 * Project list.
 * @returns {JSX.Element} The page.
 */
function ProjectsPage() {
  const { can } = useAuth();
  const list = useListParams(FILTERS, 'end_date');
  const { requestParams } = list;
  const options = useLoad(getProjectOptions);
  const projects = useLoad(useCallback(
    (signal) => listProjects(requestParams, signal),
    [requestParams],
  ));

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" component="h1">Projects</Typography>
        {can('projects:create') && (
          <Button variant="contained" component={Link} to="/projects/new">New project</Button>
        )}
      </Box>
      {options.error && (
        <ErrorState message={options.error.message} onRetry={options.reload} />
      )}
      {options.data && (
        <ProjectFilters
          filters={list.filters}
          options={options.data}
          onChange={list.update}
          onClear={list.clear}
        />
      )}
      <PagedResults
        result={projects}
        page={list.page}
        onPage={list.setPage}
        emptyTitle="No projects found"
        emptyText={list.isFiltered
          ? 'Try different filters.'
          : 'There are no projects to show yet.'}
      >
        {(items) => (
          <ProjectList
            projects={items}
            sort={list.sort}
            order={list.order}
            onSort={list.toggleSort}
          />
        )}
      </PagedResults>
    </>
  );
}

export default ProjectsPage;
