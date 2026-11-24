import { createTheme } from '@mui/material/styles';

/** Shared look of the application. */
const theme = createTheme({
  palette: {
    primary: { main: '#0b4f8a' },
    secondary: { main: '#00695c' },
    // Dark enough for text on white (WCAG AA).
    warning: { main: '#a34700' },
    background: { default: '#f4f6f8' },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: { styleOverrides: { root: { textTransform: 'none' } } },
  },
});

export default theme;
