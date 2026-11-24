import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { StatusChip } from './ProjectChips.jsx';

/**
 * Shows a linked deliverable. Hidden ones have no link.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The deliverable.
 */
function RelatedDeliverable({ item, projectCode = '', status = item.status }) {
  const code = item.project_code && item.project_code !== projectCode
    ? `${item.project_code} · `
    : '';
  const label = `${code}${item.name}`;
  return (
    <Box
      sx={{
        display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', overflowWrap: 'anywhere',
      }}
    >
      {item.id === null
        ? <Typography component="span">{label}</Typography>
        : <MuiLink component={Link} to={`/deliverables/${item.id}`}>{label}</MuiLink>}
      <StatusChip status={status} />
    </Box>
  );
}

RelatedDeliverable.propTypes = {
  item: PropTypes.shape({
    id: PropTypes.number,
    name: PropTypes.string.isRequired,
    project_code: PropTypes.string,
    status: PropTypes.string.isRequired,
  }).isRequired,
  projectCode: PropTypes.string,
  status: PropTypes.string,
};

export default RelatedDeliverable;
