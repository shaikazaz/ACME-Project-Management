import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useCallback, useState } from 'react';
import CategoryDialog from '../components/CategoryDialog.jsx';
import DateField from '../components/DateField.jsx';
import ExpenseList from '../components/ExpenseList.jsx';
import FilterPanel from '../components/FilterPanel.jsx';
import { ErrorState } from '../components/PageStates.jsx';
import PagedResults from '../components/PagedResults.jsx';
import SelectField from '../components/SelectField.jsx';
import { useAuth } from '../context/contexts.js';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import { getExpenseOptions, listExpenses } from '../services/budgetService.js';
import { formatMoney } from '../utils/format.js';

const FILTERS = [
  'search', 'project_id', 'category_id', 'date_from', 'date_to', 'amount_min',
];
const SORTS = [
  { id: 'expense_date', name: 'Date' },
  { id: 'amount', name: 'Amount' },
  { id: 'category', name: 'Category' },
  { id: 'project', name: 'Project' },
];

/**
 * Expenses of the projects the user manages.
 * @returns {JSX.Element} The page.
 */
function ExpensesPage() {
  const { can } = useAuth();
  const [managing, setManaging] = useState(false);
  const list = useListParams(FILTERS, 'expense_date', 'desc');
  const { filters, requestParams } = list;
  const options = useLoad(getExpenseOptions);
  const expenses = useLoad(useCallback(
    (signal) => listExpenses(requestParams, signal),
    [requestParams],
  ));
  const field = (name) => ({
    value: filters[name],
    onChange: (event) => list.update({ [name]: event.target.value }),
  });
  // Ignore half-typed amounts such as "12." instead of sending them.
  const handleAmount = (event) => {
    const { value } = event.target;
    if (/^\d{0,12}(\.\d{1,2})?$/.test(value)) list.update({ amount_min: value });
  };

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" component="h1">Expenses</Typography>
        {can('settings:manage') && (
          <Button onClick={() => setManaging(true)}>Categories</Button>
        )}
      </Box>
      {options.error && (
        <ErrorState message={options.error.message} onRetry={options.reload} />
      )}
      {options.data && (
        <FilterPanel search={filters.search} onChange={list.update} onClear={list.clear}>
          <SelectField
            label="Project"
            options={options.data.projects}
            emptyLabel="All projects"
            {...field('project_id')}
          />
          <SelectField
            label="Category"
            options={options.data.categories}
            emptyLabel="All categories"
            {...field('category_id')}
          />
          <DateField label="From" {...field('date_from')} />
          <DateField label="Until" {...field('date_to')} />
          <TextField
            size="small"
            type="number"
            label="Minimum amount"
            value={filters.amount_min}
            onChange={handleAmount}
            slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
          />
          <SelectField
            label="Sort by"
            options={SORTS}
            value={list.sort}
            onChange={(event) => list.update({ sort: event.target.value })}
          />
        </FilterPanel>
      )}
      {expenses.data && !expenses.error && (
        <Typography sx={{ mb: 1 }}>
          {`Total: ${formatMoney(expenses.data.total_amount)}`}
        </Typography>
      )}
      <PagedResults
        result={expenses}
        page={list.page}
        onPage={list.setPage}
        emptyTitle="No expenses found"
        emptyText={list.isFiltered
          ? 'Try different filters.'
          : 'Expenses of the projects you manage appear here.'}
      >
        {(items) => <ExpenseList expenses={items} onChanged={expenses.reload} />}
      </PagedResults>
      {managing && (
        <CategoryDialog
          onClose={() => {
            setManaging(false);
            options.reload();
            expenses.reload();
          }}
        />
      )}
    </>
  );
}

export default ExpensesPage;
