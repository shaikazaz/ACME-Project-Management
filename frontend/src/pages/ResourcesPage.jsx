import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState } from '../components/PageStates.jsx';
import PagedResults from '../components/PagedResults.jsx';
import ResourceFilters from '../components/ResourceFilters.jsx';
import ResourceList from '../components/ResourceList.jsx';
import { useAuth } from '../context/contexts.js';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import { getResourceOptions, listResources } from '../services/resourceService.js';

const FILTERS = ['search', 'department_id', 'availability', 'skill', 'over_allocated'];

/**
 * Resource list.
 * @returns {JSX.Element} The page.
 */
function ResourcesPage() {
  const { can } = useAuth();
  const list = useListParams(FILTERS, 'name');
  const { requestParams } = list;
  const options = useLoad(getResourceOptions);
  const resources = useLoad(useCallback(
    (signal) => listResources(requestParams, signal),
    [requestParams],
  ));

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" component="h1">Resources</Typography>
        {can('resources:manage') && (
          <Button variant="contained" component={Link} to="/resources/new">
            New resource
          </Button>
        )}
      </Box>
      {options.error && (
        <ErrorState message={options.error.message} onRetry={options.reload} />
      )}
      {options.data && (
        <ResourceFilters
          filters={list.filters}
          options={options.data}
          onChange={list.update}
          onClear={list.clear}
        />
      )}
      <PagedResults
        result={resources}
        page={list.page}
        onPage={list.setPage}
        emptyTitle="No resources found"
        emptyText={list.isFiltered
          ? 'Try different filters.'
          : 'There are no resources to show yet.'}
      >
        {(items) => (
          <ResourceList
            resources={items}
            sort={list.sort}
            order={list.order}
            onSort={list.toggleSort}
          />
        )}
      </PagedResults>
    </>
  );
}

export default ResourcesPage;
