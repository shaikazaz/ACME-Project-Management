import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';

/**
 * One number with a label, which may link to the details.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The tile.
 */
export function Tile({ label, value, to = '' }) {
  return (
    <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column-reverse' }}>
      <Typography variant="body2" component="dt" sx={{ color: 'text.secondary' }}>
        {to ? <MuiLink component={Link} to={to} color="inherit">{label}</MuiLink> : label}
      </Typography>
      <Typography variant="h5" component="dd" sx={{ m: 0, overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Paper>
  );
}

Tile.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  to: PropTypes.string,
};

/**
 * Lays out tiles.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The tiles.
 */
export function TileGrid({ children }) {
  return (
    <Box
      component="dl"
      sx={{
        m: 0,
        mb: 3,
        display: 'grid',
        gap: 2,
        gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' },
      }}
    >
      {children}
    </Box>
  );
}

TileGrid.propTypes = { children: PropTypes.node.isRequired };
