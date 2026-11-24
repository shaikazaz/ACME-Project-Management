import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import DeliverableFilters from '../components/DeliverableFilters.jsx';
import DeliverableList from '../components/DeliverableList.jsx';
import { ErrorState } from '../components/PageStates.jsx';
import PagedResults from '../components/PagedResults.jsx';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import { getDeliverableOptions, listDeliverables } from '../services/deliverableService.js';

const FILTERS = [
  'search', 'project_id', 'status', 'priority', 'owner_id', 'overdue', 'due_to',
];
const loadOptions = (signal) => getDeliverableOptions(undefined, signal);

/**
 * List of the deliverables the user may view, across projects.
 * @returns {JSX.Element} The page.
 */
function DeliverablesPage() {
  const list = useListParams(FILTERS, 'due_date');
  const { requestParams } = list;
  const options = useLoad(loadOptions);
  const deliverables = useLoad(useCallback(
    (signal) => listDeliverables(requestParams, signal),
    [requestParams],
  ));

  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>Deliverables</Typography>
      {options.error && (
        <ErrorState message={options.error.message} onRetry={options.reload} />
      )}
      {options.data && (
        <DeliverableFilters
          filters={list.filters}
          options={options.data}
          onChange={list.update}
          onClear={list.clear}
        />
      )}
      <PagedResults
        result={deliverables}
        page={list.page}
        onPage={list.setPage}
        emptyTitle="No deliverables found"
        emptyText={list.isFiltered
          ? 'Try different filters.'
          : 'There are no deliverables to show yet.'}
      >
        {(items) => (
          <DeliverableList
            deliverables={items}
            sort={list.sort}
            order={list.order}
            onSort={list.toggleSort}
          />
        )}
      </PagedResults>
    </>
  );
}

export default DeliverablesPage;
