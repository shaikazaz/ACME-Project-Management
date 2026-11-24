import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';

const COLORS = { 'On Track': 'success', Warning: 'warning', 'Over Budget': 'error' };

/**
 * Shows how much of a budget is consumed.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The bar.
 */
function BudgetBar({ budget }) {
  const { consumed_percent: consumed, status } = budget;
  const fallback = status === 'Over Budget' ? 100 : 0;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 110 }}>
      <LinearProgress
        variant="determinate"
        color={COLORS[status] ?? 'inherit'}
        value={Math.min(100, consumed ?? fallback)}
        aria-label="Budget consumed"
        sx={{ flexGrow: 1 }}
      />
      <Typography variant="body2">{consumed === null ? '—' : `${consumed}%`}</Typography>
    </Box>
  );
}

BudgetBar.propTypes = {
  budget: PropTypes.shape({
    consumed_percent: PropTypes.number,
    status: PropTypes.string.isRequired,
  }).isRequired,
};

export default BudgetBar;
