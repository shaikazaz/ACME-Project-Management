import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import { createExpense, getProjectBudget, listExpenses } from '../services/budgetService.js';
import { describeBudgetProblem } from '../utils/expenseForm.js';
import { formatMoney } from '../utils/format.js';
import BudgetAlert from './BudgetAlert.jsx';
import BudgetBar from './BudgetBar.jsx';
import BudgetChip from './BudgetChip.jsx';
import ExpenseDialog from './ExpenseDialog.jsx';
import ExpenseList from './ExpenseList.jsx';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';
import { Tile, TileGrid } from './Tiles.jsx';

const LIMIT = 100;

function Breakdown({ title, rows }) {
  return (
    <Paper component="section" sx={{ p: 2 }}>
      <Typography variant="h6" component="h2">{title}</Typography>
      <Box component="ul" aria-label={title} sx={{ m: 0, pl: 3 }}>
        {rows.map(({ key, label, amount }) => (
          <li key={key}>{`${label}: ${formatMoney(amount)}`}</li>
        ))}
      </Box>
    </Paper>
  );
}

Breakdown.propTypes = {
  title: PropTypes.string.isRequired,
  rows: PropTypes.arrayOf(PropTypes.object).isRequired,
};

/**
 * A project's budget and expenses.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The section.
 */
function ProjectBudget({ projectId }) {
  const notify = useNotify();
  const [adding, setAdding] = useState(false);
  const { data, error, reload } = useLoad(useCallback(async (signal) => {
    const [budget, expenses] = await Promise.all([
      getProjectBudget(projectId, signal),
      listExpenses({ project_id: projectId, limit: LIMIT }, signal),
    ]);
    return { budget, expenses };
  }, [projectId]));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading budget" />;
  const { budget, expenses } = data;

  const handleCreate = async (values) => {
    const saved = await createExpense(projectId, values);
    setAdding(false);
    const problem = describeBudgetProblem(saved.budget, formatMoney);
    notify(`Expense added. ${problem}`.trim(), problem ? 'warning' : 'success');
    reload();
  };

  return (
    <>
      <BudgetAlert budget={budget} />
      <TileGrid>
        <Tile label="Planned budget" value={formatMoney(budget.planned)} />
        <Tile label="Actual spending" value={formatMoney(budget.actual)} />
        <Tile label="Remaining" value={formatMoney(budget.remaining)} />
        <Tile
          label="Consumed"
          value={budget.consumed_percent === null ? '—' : `${budget.consumed_percent}%`}
        />
      </TileGrid>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
        <BudgetChip status={budget.status} />
        <Box sx={{ flexGrow: 1 }}><BudgetBar budget={budget} /></Box>
        <Button variant="contained" onClick={() => setAdding(true)}>New expense</Button>
      </Box>
      {expenses.items.length === 0 ? (
        <EmptyState title="No expenses yet" text="Expenses reduce the remaining budget." />
      ) : (
        <>
          <Box
            sx={{
              display: 'grid', gap: 2, mb: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            }}
          >
            <Breakdown
              title="By category"
              rows={budget.categories.map(({ category, amount, share_percent: share }) => ({
                key: category.id, label: `${category.name} (${share}%)`, amount,
              }))}
            />
            <Breakdown
              title="By month"
              rows={budget.months.map(({ month, amount }) => ({
                key: month, label: month, amount,
              }))}
            />
          </Box>
          <ExpenseList expenses={expenses.items} showProject={false} onChanged={reload} />
        </>
      )}
      {expenses.total > LIMIT && (
        <Button component={Link} to={`/expenses?project_id=${projectId}`}>
          {`Show all ${expenses.total}`}
        </Button>
      )}
      {adding && (
        <ExpenseDialog onCancel={() => setAdding(false)} onSubmit={handleCreate} />
      )}
    </>
  );
}

ProjectBudget.propTypes = { projectId: PropTypes.number.isRequired };

export default ProjectBudget;
