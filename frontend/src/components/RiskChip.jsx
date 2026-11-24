import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlined';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Chip from '@mui/material/Chip';
import PropTypes from 'prop-types';

// An icon and a word, so the level never depends on colour alone.
const LEVELS = {
  High: { color: 'error', icon: <ErrorOutlineIcon /> },
  Medium: { color: 'warning', icon: <WarningAmberIcon /> },
  Low: { color: 'success', icon: <TaskAltIcon /> },
};

/**
 * Shows a risk level.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chip.
 */
function RiskChip({ level }) {
  const { color, icon } = LEVELS[level];
  return (
    <Chip size="small" variant="outlined" color={color} icon={icon} label={`${level} risk`} />
  );
}

RiskChip.propTypes = { level: PropTypes.oneOf(['High', 'Medium', 'Low']).isRequired };

export default RiskChip;
