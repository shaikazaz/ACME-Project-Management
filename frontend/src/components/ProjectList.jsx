import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { formatDate, formatMoney } from '../utils/format.js';
import BudgetChip from './BudgetChip.jsx';
import DataList from './DataList.jsx';
import { PriorityChip, ProgressBar, StatusChip } from './ProjectChips.jsx';
import RiskChip from './RiskChip.jsx';

const linkTo = (project) => `/projects/${project.id}`;

const COLUMNS = [
  {
    label: 'Code', sort: 'code', nowrap: true, render: (project) => project.code,
  },
  {
    label: 'Project',
    sort: 'name',
    render: (project) => (
      <MuiLink component={Link} to={linkTo(project)}>{project.name}</MuiLink>
    ),
  },
  { label: 'Department', render: (project) => project.department.name },
  { label: 'Manager', render: (project) => project.manager?.name ?? '—' },
  {
    label: 'Status',
    sort: 'status',
    render: (project) => <StatusChip status={project.status} />,
  },
  {
    label: 'Risk',
    render: (project) => (project.risk ? <RiskChip level={project.risk.level} /> : '—'),
  },
  {
    label: 'Priority',
    sort: 'priority',
    render: (project) => <PriorityChip priority={project.priority} />,
  },
  {
    label: 'Ends',
    sort: 'end_date',
    nowrap: true,
    render: (project) => formatDate(project.end_date),
  },
  {
    label: 'Progress',
    sort: 'progress',
    render: (project) => <ProgressBar value={project.progress_percent} />,
  },
  {
    label: 'Budget',
    align: 'right',
    render: (project) => (
      <>
        {formatMoney(project.planned_budget)}
        {project.budget?.status === 'Over Budget' && (
          <div><BudgetChip status={project.budget.status} /></div>
        )}
      </>
    ),
  },
];

function renderCard(project) {
  return (
    <>
      <Typography variant="overline">{project.code}</Typography>
      <Typography variant="h6" component="h2" sx={{ overflowWrap: 'anywhere' }}>
        {project.name}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <StatusChip status={project.status} />
        <PriorityChip priority={project.priority} />
        {project.risk && <RiskChip level={project.risk.level} />}
      </Box>
      <Typography variant="body2">
        {`${project.department.name} · ends ${formatDate(project.end_date)}`}
      </Typography>
      <ProgressBar value={project.progress_percent} />
    </>
  );
}

/**
 * Lists projects.
 * @param {Object} props Component props; sorting props go to the list.
 * @returns {JSX.Element} The list.
 */
function ProjectList({ projects, ...props }) {
  return (
    <DataList
      label="Projects"
      rows={projects}
      columns={COLUMNS}
      linkTo={linkTo}
      renderCard={renderCard}
      {...props}
    />
  );
}

ProjectList.propTypes = { projects: PropTypes.arrayOf(PropTypes.object).isRequired };

export default ProjectList;
