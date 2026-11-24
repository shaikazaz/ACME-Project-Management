import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { Link } from 'react-router-dom';

/**
 * Shown for unknown addresses.
 * @returns {JSX.Element} The page.
 */
function NotFoundPage() {
  return (
    <>
      <Typography variant="h4" component="h1" gutterBottom>Page not found</Typography>
      <Button component={Link} to="/projects" variant="contained">Go to projects</Button>
    </>
  );
}

export default NotFoundPage;
