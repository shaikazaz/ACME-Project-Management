import MuiLink from '@mui/material/Link';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { describeBlockers } from '../utils/deliverableForm.js';
import { formatDate } from '../utils/format.js';
import DataList from './DataList.jsx';
import DeliverableStatus from './DeliverableStatus.jsx';
import { PriorityChip, ProgressBar } from './ProjectChips.jsx';

const linkTo = (item) => `/deliverables/${item.id}`;

const PROJECT_COLUMN = {
  label: 'Project', sort: 'project', nowrap: true, render: (item) => item.project.code,
};

const COLUMNS = [
  {
    label: 'Deliverable',
    sort: 'name',
    render: (item) => (
      <>
        <MuiLink component={Link} to={linkTo(item)}>{item.name}</MuiLink>
        {item.blocked_by.length > 0 && (
          <Typography variant="caption" component="div" sx={{ color: 'text.secondary' }}>
            {describeBlockers(item.blocked_by)}
          </Typography>
        )}
      </>
    ),
  },
  { label: 'Owner', render: (item) => item.owner?.name ?? '—' },
  { label: 'Status', sort: 'status', render: (item) => <DeliverableStatus deliverable={item} /> },
  {
    label: 'Priority',
    sort: 'priority',
    render: (item) => <PriorityChip priority={item.priority} />,
  },
  {
    label: 'Due', sort: 'due_date', nowrap: true, render: (item) => formatDate(item.due_date),
  },
  {
    label: 'Progress',
    sort: 'progress',
    render: (item) => <ProgressBar value={item.progress_percent} />,
  },
  {
    label: 'Hours',
    nowrap: true,
    align: 'right',
    render: (item) => `${item.actual_hours} / ${item.estimated_hours}`,
  },
];

function renderCard(item) {
  return (
    <>
      <Typography variant="overline">{item.project.code}</Typography>
      <Typography variant="h6" component="h2" sx={{ overflowWrap: 'anywhere' }}>
        {item.name}
      </Typography>
      <DeliverableStatus deliverable={item} />
      {item.blocked_by.length > 0 && (
        <Typography variant="body2">{describeBlockers(item.blocked_by)}</Typography>
      )}
      <Typography variant="body2">
        {`${item.owner?.name ?? 'No owner'} · due ${formatDate(item.due_date)}`}
      </Typography>
      <ProgressBar value={item.progress_percent} />
    </>
  );
}

/**
 * Lists deliverables.
 * @param {Object} props Component props; sorting props go to the list.
 * @returns {JSX.Element} The list.
 */
function DeliverableList({ deliverables, showProject = true, ...props }) {
  return (
    <DataList
      label="Deliverables"
      rows={deliverables}
      columns={showProject ? [PROJECT_COLUMN, ...COLUMNS] : COLUMNS}
      linkTo={linkTo}
      renderCard={renderCard}
      {...props}
    />
  );
}

DeliverableList.propTypes = {
  deliverables: PropTypes.arrayOf(PropTypes.object).isRequired,
  showProject: PropTypes.bool,
};

export default DeliverableList;
