import PropTypes from 'prop-types';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/contexts.js';
import { ErrorState, LoadingState } from './PageStates.jsx';

/**
 * Shows a page only to users who may open it. The backend enforces the rules;
 * this only avoids showing pages that cannot work.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The page, a redirect or a message.
 */
function ProtectedRoute({ children, permission = null }) {
  const { status, retry, can } = useAuth();
  const location = useLocation();

  if (status === 'loading') return <LoadingState label="Signing you in" />;
  if (status === 'failed') {
    return <ErrorState message="Cannot reach the server." onRetry={retry} />;
  }
  if (status === 'signedOut') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (permission && !can(permission)) {
    return <ErrorState message="You do not have permission to open this page." />;
  }
  return children;
}

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
  permission: PropTypes.string,
};

export default ProtectedRoute;
