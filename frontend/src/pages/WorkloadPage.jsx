import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback } from 'react';
import DateField from '../components/DateField.jsx';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import PagedResults from '../components/PagedResults.jsx';
import ResourceList from '../components/ResourceList.jsx';
import { Tile, TileGrid } from '../components/Tiles.jsx';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import { getWorkloadReport, listResources } from '../services/resourceService.js';
import { formatDate } from '../utils/format.js';

const PERIOD = ['period_from', 'period_to'];

const percent = (value) => (value === null ? '—' : `${value}%`);

function Report({ report }) {
  const end = report.period_to ? formatDate(report.period_to) : 'open end';
  return (
    <>
      <Typography sx={{ color: 'text.secondary', mb: 2 }}>
        {`Highest load of each person, ${formatDate(report.period_from)} to ${end}`}
      </Typography>
      <TileGrid>
        <Tile label="People" value={report.resource_count} />
        <Tile label="Over-allocated" value={report.over_allocated_count} />
        <Tile label="Fully allocated" value={report.fully_allocated_count} />
        <Tile label="Partly allocated" value={report.partly_allocated_count} />
        <Tile label="Not allocated" value={report.unallocated_count} />
        <Tile label="Need cover today" value={report.needs_cover_count} />
        <Tile label="Utilization" value={percent(report.utilization_percent)} />
      </TileGrid>
      <Typography variant="h6" component="h2">By department</Typography>
      <TableContainer component={Paper} sx={{ mb: 3 }}>
        <Table size="small" aria-label="Workload by department">
          <TableHead>
            <TableRow>
              <TableCell>Department</TableCell>
              <TableCell align="right">People</TableCell>
              <TableCell align="right">Over-allocated</TableCell>
              <TableCell align="right">Utilization</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {report.departments.map((row) => (
              <TableRow key={row.department.id}>
                <TableCell sx={{ overflowWrap: 'anywhere' }}>{row.department.name}</TableCell>
                <TableCell align="right">{row.resource_count}</TableCell>
                <TableCell align="right">{row.over_allocated_count}</TableCell>
                <TableCell align="right">{percent(row.utilization_percent)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}

Report.propTypes = {
  report: PropTypes.shape({
    period_from: PropTypes.string.isRequired,
    period_to: PropTypes.string,
    departments: PropTypes.arrayOf(PropTypes.object).isRequired,
  }).isRequired,
};

/**
 * Workload report for a period.
 * @returns {JSX.Element} The page.
 */
function WorkloadPage() {
  // The busiest people come first.
  const list = useListParams(PERIOD, 'utilization', 'desc');
  const { filters, requestParams } = list;
  const report = useLoad(useCallback(
    (signal) => getWorkloadReport(filters, signal),
    [filters],
  ));
  const resources = useLoad(useCallback(
    (signal) => listResources(requestParams, signal),
    [requestParams],
  ));
  const field = (name) => ({
    value: filters[name],
    onChange: (event) => list.update({ [name]: event.target.value }),
  });

  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>Workload</Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <DateField label="From" {...field('period_from')} />
        <DateField label="Until" {...field('period_to')} />
        <Button onClick={list.clear}>From today</Button>
      </Box>
      {report.error && (
        <ErrorState message={report.error.message} onRetry={report.reload} />
      )}
      {!report.error && !report.data && <LoadingState label="Loading report" />}
      {!report.error && report.data && <Report report={report.data} />}
      <Typography variant="h6" component="h2">By person</Typography>
      <PagedResults
        result={resources}
        page={list.page}
        onPage={list.setPage}
        emptyTitle="No resources found"
        emptyText="There are no resources to show yet."
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

export default WorkloadPage;
