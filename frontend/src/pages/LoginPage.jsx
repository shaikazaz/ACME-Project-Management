import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import DemoAccounts from '../components/DemoAccounts.jsx';
import { ErrorState, LoadingState } from '../components/PageStates.jsx';
import { useAuth } from '../context/contexts.js';

/**
 * Reads the demo accounts: local ones from .env.development.local, and the
 * shared ones of the live website from .env.production.local. Git ignores both.
 * @returns {Object[]} The accounts; empty when there are none.
 */
function readDemoAccounts() {
  try {
    return JSON.parse(import.meta.env.VITE_DEMO_ACCOUNTS ?? '[]');
  } catch {
    return [];
  }
}

/**
 * Sign-in page.
 * @returns {JSX.Element} The page.
 */
function LoginPage() {
  const { status, login, retry } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (status === 'loading') return <LoadingState label="Signing you in" />;
  if (status === 'failed') {
    return <ErrorState message="Cannot reach the server." onRetry={retry} />;
  }
  if (status === 'signedIn') {
    return <Navigate to={location.state?.from ?? '/'} replace />;
  }

  const demoAccounts = readDemoAccounts();

  const signIn = async (userEmail, userPassword) => {
    setBusy(true);
    setError('');
    try {
      await login(userEmail, userPassword);
    } catch (failure) {
      setError(failure.code === 'validation_error'
        ? 'Enter a valid email and password.'
        : failure.message);
      setBusy(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    await signIn(email, password);
  };

  return (
    <Container component="main" maxWidth="xs" sx={{ pt: { xs: 4, sm: 12 } }}>
      <Paper component="form" noValidate onSubmit={handleSubmit} sx={{ p: 4 }}>
        <Typography variant="h5" component="h1" gutterBottom>ACME Projects</Typography>
        <Typography sx={{ color: 'text.secondary', mb: 2 }}>
          Sign in to continue
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
        <TextField
          fullWidth
          margin="normal"
          type="email"
          label="Email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextField
          fullWidth
          margin="normal"
          type="password"
          label="Password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Box sx={{ mt: 2 }}>
          <Button type="submit" variant="contained" fullWidth disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </Box>
      </Paper>
      {demoAccounts.length > 0 && (
        <DemoAccounts accounts={demoAccounts} disabled={busy} onUse={signIn} />
      )}
    </Container>
  );
}

export default LoginPage;
