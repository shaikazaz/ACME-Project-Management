import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';

/**
 * Lists demo accounts for quick sign-in. Only for local development.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The list.
 */
function DemoAccounts({ accounts, disabled, onUse }) {
  return (
    <Alert severity="info" icon={false} sx={{ mt: 2, '& .MuiAlert-message': { width: '100%' } }}>
      <Typography variant="subtitle2" component="h2">
        Demo accounts (local development only)
      </Typography>
      {accounts.map(({ label, email, password }) => (
        <Box key={email} sx={{ mt: 1.5, overflowWrap: 'anywhere' }}>
          <Typography variant="body2">{`Email: ${email}`}</Typography>
          <Typography variant="body2">{`Password: ${password}`}</Typography>
          <Button
            size="small"
            variant="outlined"
            fullWidth
            sx={{ mt: 0.5 }}
            disabled={disabled}
            onClick={() => onUse(email, password)}
          >
            {`Sign in as ${label}`}
          </Button>
        </Box>
      ))}
    </Alert>
  );
}

DemoAccounts.propTypes = {
  accounts: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    email: PropTypes.string.isRequired,
    password: PropTypes.string.isRequired,
  })).isRequired,
  disabled: PropTypes.bool.isRequired,
  onUse: PropTypes.func.isRequired,
};

export default DemoAccounts;
