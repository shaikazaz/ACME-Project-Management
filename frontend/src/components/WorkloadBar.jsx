import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';

/**
 * Shows a person's peak allocation against their own capacity.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The bar.
 */
function WorkloadBar({ workload }) {
  const {
    peak_percent: peak, capacity_percent: capacity, utilization_percent: utilization,
    is_over_allocated: over, is_over_allocated_now: overNow,
  } = workload;
  const label = over ? 'Over-allocated' : null;
  return (
    <Box sx={{ minWidth: 140 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
        <Typography variant="body2">{`${peak}% of ${capacity}%`}</Typography>
        {label && (
          <Chip
            size="small"
            color="error"
            variant={overNow ? 'filled' : 'outlined'}
            label={overNow ? label : `${label} later`}
          />
        )}
      </Box>
      <LinearProgress
        variant="determinate"
        color={over ? 'error' : 'primary'}
        value={Math.min(100, utilization ?? (peak > 0 ? 100 : 0))}
        aria-label={`Utilization ${utilization ?? 'without capacity'}`}
      />
    </Box>
  );
}

WorkloadBar.propTypes = {
  workload: PropTypes.shape({
    peak_percent: PropTypes.number.isRequired,
    capacity_percent: PropTypes.number.isRequired,
    utilization_percent: PropTypes.number,
    is_over_allocated: PropTypes.bool.isRequired,
    is_over_allocated_now: PropTypes.bool.isRequired,
  }).isRequired,
};

export default WorkloadBar;
