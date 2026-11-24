import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { formatDate, formatDateTime, formatMoney } from '../utils/format.js';
import BudgetBar from './BudgetBar.jsx';
import { Fact, FactList } from './Facts.jsx';
import { PriorityChip, ProgressBar, StatusChip } from './ProjectChips.jsx';

/**
 * The main facts of a project.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The section.
 */
function ProjectOverview({ project }) {
  return (
    <Paper sx={{ p: 3 }}>
      <FactList>
        <Fact label="Status"><StatusChip status={project.status} /></Fact>
        <Fact label="Priority"><PriorityChip priority={project.priority} /></Fact>
        <Fact label="Progress"><ProgressBar value={project.progress_percent} /></Fact>
        <Fact label="Department">{project.department.name}</Fact>
        <Fact label="Project manager">{project.manager?.name ?? 'Not assigned'}</Fact>
        {project.budget && (
          <>
            <Fact label="Planned budget">{formatMoney(project.budget.planned)}</Fact>
            <Fact label="Actual spending">{formatMoney(project.budget.actual)}</Fact>
            <Fact label="Remaining budget">{formatMoney(project.budget.remaining)}</Fact>
            <Fact label="Budget consumed"><BudgetBar budget={project.budget} /></Fact>
          </>
        )}
        <Fact label="Start date">{formatDate(project.start_date)}</Fact>
        <Fact label="End date">{formatDate(project.end_date)}</Fact>
        <Fact label="Completed on">{formatDate(project.actual_completion_date)}</Fact>
        <Fact label="Last updated">{formatDateTime(project.updated_at)}</Fact>
      </FactList>
      <Typography variant="h6" component="h2" sx={{ mt: 3 }}>Description</Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
        {project.description || 'No description.'}
      </Typography>
    </Paper>
  );
}

ProjectOverview.propTypes = {
  project: PropTypes.shape({
    status: PropTypes.string.isRequired,
    priority: PropTypes.string.isRequired,
    description: PropTypes.string,
  }).isRequired,
};

export default ProjectOverview;
