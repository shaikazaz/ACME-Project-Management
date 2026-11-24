import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotify } from '../context/contexts.js';
import useScreen from '../hooks/useScreen.js';
import { deleteExpense, updateExpense } from '../services/budgetService.js';
import { describeBudgetProblem } from '../utils/expenseForm.js';
import { formatDate, formatMoney } from '../utils/format.js';
import ConfirmDialog from './ConfirmDialog.jsx';
import ExpenseDialog from './ExpenseDialog.jsx';

/**
 * Lists expenses and lets the user edit and delete them.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The list.
 */
function ExpenseList({ expenses, showProject = true, onChanged }) {
  const notify = useNotify();
  const { isMobile } = useScreen();
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const handleSave = async (values) => {
    const { budget } = await updateExpense(editing.id, values);
    setEditing(null);
    const problem = describeBudgetProblem(budget, formatMoney);
    notify(`Expense saved. ${problem}`.trim(), problem ? 'warning' : 'success');
    onChanged();
  };
  const handleDelete = async () => {
    await deleteExpense(deleting.id);
    setDeleting(null);
    notify('Expense deleted');
    onChanged();
  };

  const project = (item) => (
    <MuiLink component={Link} to={`/projects/${item.project.id}?tab=budget`}>
      {item.project.code}
    </MuiLink>
  );
  const actions = (item) => (
    <Box sx={{ display: 'flex' }}>
      <Button
        size="small"
        onClick={() => setEditing(item)}
        aria-label={`Edit ${item.description}`}
      >
        Edit
      </Button>
      <Button
        size="small"
        color="error"
        onClick={() => setDeleting(item)}
        aria-label={`Delete ${item.description}`}
      >
        Delete
      </Button>
    </Box>
  );

  return (
    <>
      {isMobile ? (
        <Box sx={{ display: 'grid', gap: 2 }}>
          {expenses.map((item) => (
            <Paper key={item.id} sx={{ p: 2, overflowWrap: 'anywhere' }}>
              <Typography variant="h6" component="p">{formatMoney(item.amount)}</Typography>
              <Typography>{item.description}</Typography>
              <Typography variant="body2">
                {showProject && project(item)}
                {`${showProject ? ' · ' : ''}${item.category.name} · `
                  + `${formatDate(item.expense_date)}`}
              </Typography>
              {actions(item)}
            </Paper>
          ))}
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small" aria-label="Expenses">
            <TableHead>
              <TableRow>
                {showProject && <TableCell>Project</TableCell>}
                <TableCell>Date</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Added by</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {expenses.map((item) => (
                <TableRow key={item.id} hover>
                  {showProject && <TableCell>{project(item)}</TableCell>}
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatDate(item.expense_date)}
                  </TableCell>
                  <TableCell>{item.category.name}</TableCell>
                  <TableCell sx={{ overflowWrap: 'anywhere' }}>{item.description}</TableCell>
                  <TableCell>{item.created_by?.name ?? '—'}</TableCell>
                  <TableCell align="right">{formatMoney(item.amount)}</TableCell>
                  <TableCell>{actions(item)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {editing && (
        <ExpenseDialog
          expense={editing}
          onCancel={() => setEditing(null)}
          onSubmit={handleSave}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete this expense?"
          text={`${deleting.description}: ${formatMoney(deleting.amount)}`}
          confirmLabel="Delete expense"
          onCancel={() => setDeleting(null)}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

ExpenseList.propTypes = {
  expenses: PropTypes.arrayOf(PropTypes.object).isRequired,
  showProject: PropTypes.bool,
  onChanged: PropTypes.func.isRequired,
};

export default ExpenseList;
