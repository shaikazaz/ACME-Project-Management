import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import PropTypes from 'prop-types';

const COLORS = { Available: 'success', 'On Leave': 'warning' };

/**
 * Shows a person's availability, and whether their work needs cover.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chips.
 */
function AvailabilityChip({ availability, needsCover = false }) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      <Chip size="small" label={availability} color={COLORS[availability] ?? 'default'} />
      {needsCover && (
        <Chip size="small" color="error" variant="outlined" label="Needs cover" />
      )}
    </Box>
  );
}

AvailabilityChip.propTypes = {
  availability: PropTypes.string.isRequired,
  needsCover: PropTypes.bool,
};

export default AvailabilityChip;
