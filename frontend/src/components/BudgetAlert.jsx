import Alert from '@mui/material/Alert';
import PropTypes from 'prop-types';
import { describeBudgetProblem } from '../utils/expenseForm.js';
import { formatMoney } from '../utils/format.js';

/**
 * Warns when a budget is nearly or more than consumed.
 * @param {Object} props Component props.
 * @returns {JSX.Element|null} The alert, if needed.
 */
function BudgetAlert({ budget }) {
  const text = describeBudgetProblem(budget, formatMoney);
  if (!text) return null;
  return (
    <Alert severity={budget.status === 'Over Budget' ? 'error' : 'warning'} sx={{ mb: 2 }}>
      {text}
    </Alert>
  );
}

BudgetAlert.propTypes = {
  budget: PropTypes.shape({
    status: PropTypes.string.isRequired,
    remaining: PropTypes.string.isRequired,
    consumed_percent: PropTypes.number,
  }).isRequired,
};

export default BudgetAlert;
