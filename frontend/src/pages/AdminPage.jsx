import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useNavigate, useParams } from 'react-router-dom';
import DepartmentSection from '../components/DepartmentSection.jsx';
import SettingSection from '../components/SettingSection.jsx';
import UserSection from '../components/UserSection.jsx';

const SECTIONS = {
  users: ['Users', UserSection],
  departments: ['Departments', DepartmentSection],
  settings: ['Settings', SettingSection],
};

/**
 * Administration of users, departments and settings.
 * @returns {JSX.Element} The page.
 */
function AdminPage() {
  const params = useParams();
  const navigate = useNavigate();
  const section = params.section in SECTIONS ? params.section : 'users';
  const Section = SECTIONS[section][1];

  return (
    <>
      <Typography variant="h4" component="h1">Administration</Typography>
      <Tabs
        value={section}
        onChange={(_, next) => navigate(`/admin/${next}`)}
        variant="scrollable"
        aria-label="Administration sections"
        sx={{ mb: 2 }}
      >
        {Object.entries(SECTIONS).map(([key, [label]]) => (
          <Tab key={key} value={key} label={label} id={`tab-${key}`} aria-controls="tab-panel" />
        ))}
      </Tabs>
      <Box role="tabpanel" id="tab-panel" aria-labelledby={`tab-${section}`}><Section /></Box>
    </>
  );
}

export default AdminPage;
