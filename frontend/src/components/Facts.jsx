import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';

/**
 * A labelled value.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The value.
 */
export function Fact({ label, children }) {
  return (
    <Box>
      <Typography component="dt" variant="caption" sx={{ color: 'text.secondary' }}>
        {label}
      </Typography>
      <Box component="dd" sx={{ m: 0, overflowWrap: 'anywhere' }}>{children}</Box>
    </Box>
  );
}

Fact.propTypes = { label: PropTypes.string.isRequired, children: PropTypes.node.isRequired };

/**
 * Lays out labelled values.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The list.
 */
export function FactList({ children }) {
  return (
    <Box
      component="dl"
      sx={{
        m: 0,
        display: 'grid',
        gap: 3,
        gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(3, 1fr)' },
      }}
    >
      {children}
    </Box>
  );
}

FactList.propTypes = { children: PropTypes.node.isRequired };
