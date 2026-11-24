import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import TablePagination from '@mui/material/TablePagination';
import PropTypes from 'prop-types';
import { PAGE_SIZE } from '../hooks/useListParams.js';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';

/**
 * Shows the loading, error, empty and filled states of a paged list.
 * @param {Object} props Component props; children renders the rows.
 * @returns {JSX.Element} The results.
 */
function PagedResults({
  result, page, onPage, emptyTitle, emptyText, children,
}) {
  if (result.error) {
    return <ErrorState message={result.error.message} onRetry={result.reload} />;
  }
  if (!result.data) return <LoadingState label="Loading list" />;
  const { items, total } = result.data;
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
  return (
    <Box aria-busy={result.loading}>
      <Box sx={{ height: 4 }}>{result.loading && <LinearProgress />}</Box>
      {items.length === 0
        ? <EmptyState title={emptyTitle} text={emptyText} />
        : children(items)}
      {total > 0 && (
        <TablePagination
          component="div"
          count={total}
          page={Math.min(page, lastPage)}
          rowsPerPage={PAGE_SIZE}
          rowsPerPageOptions={[PAGE_SIZE]}
          onPageChange={(_, next) => onPage(next)}
        />
      )}
    </Box>
  );
}

PagedResults.propTypes = {
  result: PropTypes.shape({
    data: PropTypes.shape({ items: PropTypes.array, total: PropTypes.number }),
    error: PropTypes.instanceOf(Error),
    loading: PropTypes.bool,
    reload: PropTypes.func,
  }).isRequired,
  page: PropTypes.number.isRequired,
  onPage: PropTypes.func.isRequired,
  emptyTitle: PropTypes.string.isRequired,
  emptyText: PropTypes.string.isRequired,
  children: PropTypes.func.isRequired,
};

export default PagedResults;
