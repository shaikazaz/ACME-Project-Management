import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';

/**
 * A bar per category. One colour is enough, because every bar carries its name
 * and number.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chart.
 */
function CountBars({ title, counts, linkTo }) {
  const rows = Object.entries(counts);
  const largest = Math.max(1, ...rows.map(([, count]) => count));
  return (
    <Paper component="section" sx={{ p: 2 }}>
      <Typography variant="h6" component="h2" gutterBottom>{title}</Typography>
      <Box
        component="ul"
        aria-label={title}
        sx={{
          m: 0, p: 0, listStyle: 'none', display: 'grid', gap: 1,
        }}
      >
        {rows.map(([name, count]) => (
          <Box
            component="li"
            key={name}
            title={`${name}: ${count}`}
            sx={{
              display: 'grid',
              gridTemplateColumns: '100px 1fr 36px',
              gap: 1,
              alignItems: 'center',
            }}
          >
            <MuiLink component={Link} to={linkTo(name)} variant="body2">{name}</MuiLink>
            <Box aria-hidden sx={{ bgcolor: 'action.hover', borderRadius: '0 4px 4px 0' }}>
              <Box
                sx={{
                  height: 12,
                  width: `${(count / largest) * 100}%`,
                  bgcolor: 'primary.main',
                  borderRadius: '0 4px 4px 0',
                }}
              />
            </Box>
            <Typography variant="body2" align="right">{count}</Typography>
          </Box>
        ))}
      </Box>
    </Paper>
  );
}

CountBars.propTypes = {
  title: PropTypes.string.isRequired,
  counts: PropTypes.objectOf(PropTypes.number).isRequired,
  linkTo: PropTypes.func.isRequired,
};

export default CountBars;
