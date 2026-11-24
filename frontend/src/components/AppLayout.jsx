import MenuIcon from '@mui/icons-material/Menu';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import MuiLink from '@mui/material/Link';
import ListItem from '@mui/material/ListItem';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import {
  Suspense, useEffect, useRef, useState,
} from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth, useNotify } from '../context/contexts.js';
import useScreen from '../hooks/useScreen.js';
import { changePassword } from '../services/authService.js';
import { roleName } from '../utils/userForm.js';
import ErrorBoundary from './ErrorBoundary.jsx';
import { LoadingState } from './PageStates.jsx';
import PasswordDialog from './PasswordDialog.jsx';

const LINKS = [
  { to: '/dashboard', label: 'Dashboard', permission: 'reports:view' },
  { to: '/projects', label: 'Projects' },
  { to: '/deliverables', label: 'Deliverables' },
  { to: '/resources', label: 'Resources', permission: 'resources:view' },
  { to: '/workload', label: 'Workload', permission: 'reports:view' },
  { to: '/budgets', label: 'Budgets', permission: 'budgets:manage' },
  { to: '/admin', label: 'Admin', permission: 'users:manage' },
];

/**
 * The frame around every signed-in page.
 * @returns {JSX.Element} The layout.
 */
function AppLayout() {
  const { user, logout, can } = useAuth();
  const notify = useNotify();
  const { pathname } = useLocation();
  const { isCompact } = useScreen();
  const main = useRef(null);
  const [leaving, setLeaving] = useState(false);
  const [anchor, setAnchor] = useState(null);
  const [changing, setChanging] = useState(false);
  const links = LINKS.filter(({ permission }) => !permission || can(permission));
  const isCurrent = (to) => pathname === to || pathname.startsWith(`${to}/`);
  const current = links.find(({ to }) => isCurrent(to))?.label;

  useEffect(() => {
    document.title = current ? `${current} · ACME Projects` : 'ACME Projects';
  }, [current]);

  const handleLogout = async () => {
    setAnchor(null);
    setLeaving(true);
    await logout();
  };
  const handlePassword = async (values) => {
    await changePassword(values.current_password, values.new_password);
    setChanging(false);
    notify('Password changed. Your other devices have been signed out.');
  };
  const closeMenu = () => setAnchor(null);

  return (
    <Box sx={{ minHeight: '100%' }}>
      <MuiLink
        component="button"
        type="button"
        onClick={() => main.current.focus()}
        sx={{
          position: 'absolute',
          left: -9999,
          zIndex: 'tooltip',
          p: 1,
          bgcolor: 'background.paper',
          '&:focus': { left: 8, top: 8 },
        }}
      >
        Skip to content
      </MuiLink>
      <AppBar position="sticky">
        <Toolbar component="nav" aria-label="Main" sx={{ gap: 1 }}>
          <Typography variant="h6" component="span" noWrap>ACME Projects</Typography>
          {!isCompact && links.map(({ to, label }) => (
            <Button
              key={to}
              color="inherit"
              component={Link}
              to={to}
              aria-current={isCurrent(to) ? 'page' : undefined}
              sx={isCurrent(to) ? { textDecoration: 'underline' } : undefined}
            >
              {label}
            </Button>
          ))}
          <Box sx={{ flexGrow: 1 }} />
          <IconButton
            color="inherit"
            aria-label="Menu"
            aria-haspopup="true"
            aria-expanded={Boolean(anchor)}
            onClick={(event) => setAnchor(event.currentTarget)}
          >
            <MenuIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={closeMenu}>
        <ListItem component="div" role="presentation">
          <Box>
            <Typography variant="body2">{user.full_name}</Typography>
            <Typography variant="caption">{roleName(user.role)}</Typography>
          </Box>
        </ListItem>
        <Divider />
        {isCompact && links.map(({ to, label }) => (
          <MenuItem
            key={to}
            component={Link}
            to={to}
            selected={isCurrent(to)}
            onClick={closeMenu}
          >
            {label}
          </MenuItem>
        ))}
        {isCompact && <Divider />}
        <MenuItem
          onClick={() => {
            closeMenu();
            setChanging(true);
          }}
        >
          Change password
        </MenuItem>
        <MenuItem onClick={handleLogout} disabled={leaving}>Sign out</MenuItem>
      </Menu>
      <Container
        component="main"
        maxWidth="lg"
        ref={main}
        tabIndex={-1}
        sx={{ py: 3, outline: 'none' }}
      >
        <ErrorBoundary resetKey={pathname}>
          <Suspense fallback={<LoadingState label="Loading page" />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </Container>
      {changing && (
        <PasswordDialog
          askCurrent
          title="Change password"
          onCancel={() => setChanging(false)}
          onSubmit={handlePassword}
        />
      )}
    </Box>
  );
}

export default AppLayout;
