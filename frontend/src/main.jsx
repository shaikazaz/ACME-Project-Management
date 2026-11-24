import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App.jsx';
import AuthProvider from './context/AuthProvider.jsx';
import NotificationProvider from './context/NotificationProvider.jsx';
import './index.css';
import theme from './theme.js';

// Hash URLs keep working after a refresh on static hosting (S3 and CloudFront).
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <HashRouter>
        <NotificationProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </NotificationProvider>
      </HashRouter>
    </ThemeProvider>
  </StrictMode>,
);
