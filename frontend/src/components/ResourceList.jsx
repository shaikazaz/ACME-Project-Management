import MuiLink from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import AvailabilityChip from './AvailabilityChip.jsx';
import DataList from './DataList.jsx';
import WorkloadBar from './WorkloadBar.jsx';

const linkTo = (item) => `/resources/${item.id}`;

const COLUMNS = [
  {
    label: 'Code', sort: 'code', nowrap: true, render: (item) => item.employee_code,
  },
  {
    label: 'Name',
    sort: 'name',
    render: (item) => (
      <>
        <MuiLink component={Link} to={linkTo(item)}>{item.full_name}</MuiLink>
        <Typography variant="caption" component="div" sx={{ color: 'text.secondary' }}>
          {item.job_title}
        </Typography>
      </>
    ),
  },
  { label: 'Department', sort: 'department', render: (item) => item.department.name },
  { label: 'Skills', render: (item) => item.skills.join(', ') || '—' },
  {
    label: 'Availability',
    render: (item) => (
      <AvailabilityChip availability={item.availability} needsCover={item.needs_cover} />
    ),
  },
  {
    label: 'Today',
    sort: 'current',
    align: 'right',
    render: (item) => `${item.workload.current_percent}%`,
  },
  {
    label: 'Peak load',
    sort: 'utilization',
    render: (item) => <WorkloadBar workload={item.workload} />,
  },
];

function renderCard(item) {
  return (
    <>
      <Typography variant="overline">{item.employee_code}</Typography>
      <Typography variant="h6" component="h2" sx={{ overflowWrap: 'anywhere' }}>
        {item.full_name}
      </Typography>
      <Typography variant="body2">{`${item.job_title} · ${item.department.name}`}</Typography>
      <AvailabilityChip availability={item.availability} needsCover={item.needs_cover} />
      <WorkloadBar workload={item.workload} />
    </>
  );
}

/**
 * Lists resources with their workload.
 * @param {Object} props Component props; sorting props go to the list.
 * @returns {JSX.Element} The list.
 */
function ResourceList({ resources, ...props }) {
  return (
    <DataList
      label="Resources"
      rows={resources}
      columns={COLUMNS}
      linkTo={linkTo}
      renderCard={renderCard}
      {...props}
    />
  );
}

ResourceList.propTypes = { resources: PropTypes.arrayOf(PropTypes.object).isRequired };

export default ResourceList;
