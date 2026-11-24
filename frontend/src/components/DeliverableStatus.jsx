import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import PropTypes from 'prop-types';
import { StatusChip } from './ProjectChips.jsx';

/**
 * Shows a deliverable's status after applying dependencies, and lateness.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chips.
 */
function DeliverableStatus({ deliverable }) {
  const {
    effective_status: status, is_overdue: overdue, days_overdue: days,
    completed_late: completedLate,
  } = deliverable;
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      <StatusChip status={status} />
      {overdue && (
        <Chip
          size="small"
          color="error"
          variant="outlined"
          label={`Overdue ${days} ${days === 1 ? 'day' : 'days'}`}
        />
      )}
      {completedLate && (
        <Chip size="small" color="warning" variant="outlined" label="Completed late" />
      )}
    </Box>
  );
}

DeliverableStatus.propTypes = {
  deliverable: PropTypes.shape({
    effective_status: PropTypes.string.isRequired,
    is_overdue: PropTypes.bool,
    days_overdue: PropTypes.number,
    completed_late: PropTypes.bool,
  }).isRequired,
};

export default DeliverableStatus;
