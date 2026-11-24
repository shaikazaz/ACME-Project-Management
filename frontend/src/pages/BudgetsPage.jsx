import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MuiLink from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import BudgetBar from '../components/BudgetBar.jsx';
import BudgetChip from '../components/BudgetChip.jsx';
import DataList from '../components/DataList.jsx';
import FilterPanel from '../components/FilterPanel.jsx';
import { ErrorState } from '../components/PageStates.jsx';
import PagedResults from '../components/PagedResults.jsx';
import { StatusChip } from '../components/ProjectChips.jsx';
import SelectField from '../components/SelectField.jsx';
import { Tile, TileGrid } from '../components/Tiles.jsx';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import { listBudgets } from '../services/budgetService.js';
import { getProjectOptions } from '../services/projectService.js';
import { formatMoney } from '../utils/format.js';

const FILTERS = ['search', 'budget_status', 'project_status', 'department_id', 'manager_id'];
const linkTo = (item) => `/projects/${item.id}?tab=budget`;

const COLUMNS = [
  {
    label: 'Code', sort: 'code', nowrap: true, render: (item) => item.code,
  },
  {
    label: 'Project',
    sort: 'name',
    render: (item) => <MuiLink component={Link} to={linkTo(item)}>{item.name}</MuiLink>,
  },
  {
    label: 'Project status',
    render: (item) => <StatusChip status={item.project_status} />,
  },
  {
    label: 'Planned',
    sort: 'planned',
    align: 'right',
    render: (item) => formatMoney(item.budget.planned),
  },
  {
    label: 'Actual',
    sort: 'actual',
    align: 'right',
    render: (item) => formatMoney(item.budget.actual),
  },
  {
    label: 'Remaining',
    sort: 'remaining',
    align: 'right',
    render: (item) => formatMoney(item.budget.remaining),
  },
  {
    label: 'Consumed',
    sort: 'consumed',
    render: (item) => <BudgetBar budget={item.budget} />,
  },
  { label: 'Budget', render: (item) => <BudgetChip status={item.budget.status} /> },
];

function renderCard(item) {
  return (
    <>
      <Typography variant="overline">{item.code}</Typography>
      <Typography variant="h6" component="h2" sx={{ overflowWrap: 'anywhere' }}>
        {item.name}
      </Typography>
      <Box><BudgetChip status={item.budget.status} /></Box>
      <Typography variant="body2">
        {`${formatMoney(item.budget.actual)} of ${formatMoney(item.budget.planned)}`}
      </Typography>
      <BudgetBar budget={item.budget} />
    </>
  );
}

/**
 * Budgets of the projects the user manages.
 * @returns {JSX.Element} The page.
 */
function BudgetsPage() {
  const list = useListParams(FILTERS, 'consumed', 'desc');
  const { filters, requestParams } = list;
  const options = useLoad(getProjectOptions);
  const budgets = useLoad(useCallback(
    (signal) => listBudgets(requestParams, signal),
    [requestParams],
  ));
  const totals = budgets.error ? null : budgets.data;
  const field = (name) => ({
    value: filters[name],
    onChange: (event) => list.update({ [name]: event.target.value }),
  });

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" component="h1">Budgets</Typography>
        <Button component={Link} to="/expenses">All expenses</Button>
      </Box>
      {options.error && (
        <ErrorState message={options.error.message} onRetry={options.reload} />
      )}
      {options.data && (
        <FilterPanel search={filters.search} onChange={list.update} onClear={list.clear}>
          <SelectField
            label="Budget status"
            options={options.data.budget_statuses}
            emptyLabel="All"
            {...field('budget_status')}
          />
          <SelectField
            label="Project status"
            options={options.data.statuses}
            emptyLabel="All"
            {...field('project_status')}
          />
          <SelectField
            label="Department"
            options={options.data.departments}
            emptyLabel="All departments"
            {...field('department_id')}
          />
          <SelectField
            label="Project manager"
            options={options.data.managers}
            emptyLabel="All managers"
            {...field('manager_id')}
          />
        </FilterPanel>
      )}
      {totals && (
        <TileGrid>
          <Tile label="Planned" value={formatMoney(totals.planned)} />
          <Tile label="Actual" value={formatMoney(totals.actual)} />
          <Tile label="Remaining" value={formatMoney(totals.remaining)} />
          <Tile
            label="Consumed"
            value={totals.consumed_percent === null ? '—' : `${totals.consumed_percent}%`}
          />
          <Tile label="Over budget" value={totals.by_status['Over Budget']} />
          <Tile label="Warning" value={totals.by_status.Warning} />
        </TileGrid>
      )}
      <PagedResults
        result={budgets}
        page={list.page}
        onPage={list.setPage}
        emptyTitle="No budgets found"
        emptyText={list.isFiltered
          ? 'Try different filters.'
          : 'Budgets of the projects you manage appear here.'}
      >
        {(items) => (
          <DataList
            label="Budgets"
            rows={items}
            columns={COLUMNS}
            linkTo={linkTo}
            renderCard={renderCard}
            sort={list.sort}
            order={list.order}
            onSort={list.toggleSort}
          />
        )}
      </PagedResults>
    </>
  );
}

export default BudgetsPage;
