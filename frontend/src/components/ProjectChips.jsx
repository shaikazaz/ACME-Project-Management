import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';

const STATUS_COLORS = {
  Planned: 'info',
  Active: 'primary',
  'On Hold': 'warning',
  Completed: 'success',
  Cancelled: 'default',
  'In Progress': 'primary',
  Blocked: 'error',
};
const PRIORITY_COLORS = { High: 'warning', Critical: 'error' };

/**
 * Shows the status of a project or deliverable.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chip.
 */
export function StatusChip({ status }) {
  return <Chip size="small" label={status} color={STATUS_COLORS[status] ?? 'default'} />;
}

StatusChip.propTypes = { status: PropTypes.string.isRequired };

/**
 * Shows a priority.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chip.
 */
export function PriorityChip({ priority }) {
  const color = PRIORITY_COLORS[priority] ?? 'default';
  return <Chip size="small" variant="outlined" label={priority} color={color} />;
}

PriorityChip.propTypes = { priority: PropTypes.string.isRequired };

/**
 * Shows progress as a bar and a percentage.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The bar.
 */
export function ProgressBar({ value }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 110 }}>
      <LinearProgress
        variant="determinate"
        value={value}
        aria-label="Progress"
        sx={{ flexGrow: 1 }}
      />
      <Typography variant="body2">{`${value}%`}</Typography>
    </Box>
  );
}

ProgressBar.propTypes = { value: PropTypes.number.isRequired };
