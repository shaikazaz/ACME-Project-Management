import Chip from '@mui/material/Chip';
import PropTypes from 'prop-types';

const COLORS = { 'On Track': 'success', Warning: 'warning', 'Over Budget': 'error' };

/**
 * Shows a budget status.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chip.
 */
function BudgetChip({ status }) {
  return <Chip size="small" label={status} color={COLORS[status] ?? 'default'} />;
}

BudgetChip.propTypes = { status: PropTypes.string.isRequired };

export default BudgetChip;
