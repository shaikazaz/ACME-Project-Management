import PropTypes from 'prop-types';
import { Component } from 'react';
import { ErrorState } from './PageStates.jsx';

/**
 * Shows a message instead of a blank screen when a page crashes or a part of
 * the application cannot be downloaded.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(previous) {
    const { resetKey } = this.props;
    const { failed } = this.state;
    // Opening another page gives the application a fresh start.
    if (failed && previous.resetKey !== resetKey) {
      this.setState({ failed: false });
    }
  }

  render() {
    const { failed } = this.state;
    const { children } = this.props;
    if (!failed) return children;
    return (
      <ErrorState
        message="This page could not be shown."
        onRetry={() => window.location.reload()}
      />
    );
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired,
  resetKey: PropTypes.string.isRequired,
};

export default ErrorBoundary;
