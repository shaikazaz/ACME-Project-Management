import Alert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';
import { NotificationContext } from './contexts.js';

/**
 * Shows short messages at the bottom of the screen.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The provider.
 */
function NotificationProvider({ children }) {
  const [notice, setNotice] = useState({ open: false, message: '', severity: 'success' });
  const notify = useCallback((message, severity = 'success') => {
    setNotice({ open: true, message, severity });
  }, []);
  const close = (_, reason) => {
    if (reason !== 'clickaway') setNotice((current) => ({ ...current, open: false }));
  };

  return (
    <NotificationContext.Provider value={notify}>
      {children}
      <Snackbar open={notice.open} autoHideDuration={6000} onClose={close}>
        <Alert severity={notice.severity} variant="filled" onClose={close}>
          {notice.message}
        </Alert>
      </Snackbar>
    </NotificationContext.Provider>
  );
}

NotificationProvider.propTypes = { children: PropTypes.node.isRequired };

export default NotificationProvider;
