import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { formatDate } from '../utils/format.js';

const SEVERITIES = { High: 'error', Medium: 'warning', Low: 'success' };

/**
 * Explains a project's risk.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The panel.
 */
function RiskPanel({ risk }) {
  const forecast = risk.forecast_end_date
    ? ` At the current pace it ends on ${formatDate(risk.forecast_end_date)}.`
    : '';
  return (
    <Alert severity={SEVERITIES[risk.level]} sx={{ mb: 2 }}>
      <AlertTitle>{`${risk.level} risk`}</AlertTitle>
      {risk.reasons.length > 0 && (
        <Box component="ul" aria-label="Risk reasons" sx={{ m: 0, pl: 3 }}>
          {risk.reasons.map(({ code, message }) => <li key={code}>{message}</li>)}
        </Box>
      )}
      <Typography variant="body2">
        {`Expected progress by now: ${risk.expected_progress_percent}%.${forecast}`}
      </Typography>
    </Alert>
  );
}

RiskPanel.propTypes = {
  risk: PropTypes.shape({
    level: PropTypes.oneOf(['High', 'Medium', 'Low']).isRequired,
    reasons: PropTypes.arrayOf(PropTypes.shape({
      code: PropTypes.string.isRequired,
      message: PropTypes.string.isRequired,
    })).isRequired,
    expected_progress_percent: PropTypes.number.isRequired,
    forecast_end_date: PropTypes.string,
  }).isRequired,
};

export default RiskPanel;
