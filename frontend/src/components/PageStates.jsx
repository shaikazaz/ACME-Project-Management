import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';

/**
 * Shows that content is loading.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The indicator.
 */
export function LoadingState({ label = 'Loading' }) {
  return (
    <Box role="status" sx={{ p: 6, textAlign: 'center' }}>
      <CircularProgress aria-label={label} />
    </Box>
  );
}

LoadingState.propTypes = { label: PropTypes.string };

/**
 * Shows that something failed, with an optional retry button.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The message.
 */
export function ErrorState({ message, onRetry = null }) {
  const action = onRetry && (
    <Button color="inherit" size="small" onClick={onRetry}>Try again</Button>
  );
  return <Alert severity="error" action={action} sx={{ my: 2 }}>{message}</Alert>;
}

ErrorState.propTypes = { message: PropTypes.string.isRequired, onRetry: PropTypes.func };

/**
 * Shows that there is nothing to list.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The message.
 */
export function EmptyState({ title, text }) {
  return (
    <Box sx={{ p: 6, textAlign: 'center' }}>
      <Typography variant="h6" component="p">{title}</Typography>
      <Typography sx={{ color: 'text.secondary' }}>{text}</Typography>
    </Box>
  );
}

EmptyState.propTypes = {
  title: PropTypes.string.isRequired,
  text: PropTypes.string.isRequired,
};
