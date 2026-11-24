import Box from '@mui/material/Box';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import CountBars from '../components/CountBars.jsx';
import { EmptyState, ErrorState, LoadingState } from '../components/PageStates.jsx';
import RiskChip from '../components/RiskChip.jsx';
import { Tile, TileGrid } from '../components/Tiles.jsx';
import useLoad from '../hooks/useLoad.js';
import getDashboard from '../services/dashboardService.js';
import { formatDate, formatMoney } from '../utils/format.js';

const percent = (value) => (value === null ? '—' : `${value}%`);
const projectsWith = (name) => (value) => `/projects?${new URLSearchParams({ [name]: value })}`;

const DEADLINE_LINKS = {
  Project: (item) => `/projects/${item.id}`,
  Milestone: (item) => `/projects/${item.project_id}?tab=milestones`,
  Deliverable: (item) => `/deliverables/${item.id}`,
};

function describeDays(days) {
  if (days === 0) return 'today';
  return days === 1 ? 'tomorrow' : `in ${days} days`;
}

function Section({ title, note = '', children }) {
  return (
    <Paper component="section" aria-label={title} sx={{ p: 2 }}>
      <Typography variant="h6" component="h2">{title}</Typography>
      {note && (
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>{note}</Typography>
      )}
      {children}
    </Paper>
  );
}

Section.propTypes = {
  title: PropTypes.string.isRequired,
  note: PropTypes.string,
  children: PropTypes.node.isRequired,
};

function RiskyProjects({ projects, total }) {
  const note = total > projects.length
    ? `The ${projects.length} most urgent of ${total}`
    : 'Most urgent first';
  return (
    <Section title="Projects at risk" note={total > 0 ? note : ''}>
      {projects.length === 0 && (
        <EmptyState title="No project is at risk" text="No risk rule applies right now." />
      )}
      <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
        {projects.map((item) => (
          <Box
            component="li"
            key={item.id}
            sx={{ py: 1, borderTop: 1, borderColor: 'divider', overflowWrap: 'anywhere' }}
          >
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              <RiskChip level={item.risk.level} />
              <MuiLink component={Link} to={`/projects/${item.id}`}>
                {`${item.code} · ${item.name}`}
              </MuiLink>
            </Box>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {`${item.status} · ${item.progress_percent}% · ends ${formatDate(item.end_date)}`
                + ` · ${item.manager?.name ?? 'no manager'}`}
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 3 }}>
              {item.risk.reasons.map(({ code, message }) => (
                <Typography component="li" variant="body2" key={code}>{message}</Typography>
              ))}
            </Box>
          </Box>
        ))}
      </Box>
      {total > projects.length && (
        <MuiLink component={Link} to="/projects?risk=High">Show all with high risk</MuiLink>
      )}
    </Section>
  );
}

RiskyProjects.propTypes = {
  projects: PropTypes.arrayOf(PropTypes.object).isRequired,
  total: PropTypes.number.isRequired,
};

function Deadlines({ deadlines, total, days }) {
  const note = total > deadlines.length
    ? `The next ${deadlines.length} of ${total}, within ${days} days`
    : `Within ${days} days`;
  return (
    <Section title="Upcoming deadlines" note={note}>
      {deadlines.length === 0 && (
        <Typography sx={{ color: 'text.secondary' }}>Nothing is due.</Typography>
      )}
      <Box component="ul" sx={{ m: 0, pl: 2 }}>
        {deadlines.map((item) => (
          <Typography
            component="li"
            variant="body2"
            key={`${item.kind}-${item.id}`}
            sx={{ overflowWrap: 'anywhere' }}
          >
            {`${formatDate(item.due_date)} (${describeDays(item.days_left)}): `}
            <MuiLink component={Link} to={DEADLINE_LINKS[item.kind](item)}>
              {item.name}
            </MuiLink>
            {` · ${item.kind} · ${item.project_code}`}
          </Typography>
        ))}
      </Box>
    </Section>
  );
}

Deadlines.propTypes = {
  deadlines: PropTypes.arrayOf(PropTypes.object).isRequired,
  total: PropTypes.number.isRequired,
  days: PropTypes.number.isRequired,
};

/**
 * Key figures of the projects the user manages.
 * @returns {JSX.Element} The page.
 */
function DashboardPage() {
  const { data, error, reload } = useLoad(getDashboard);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading dashboard" />;
  const {
    projects, deliverables, resources, budget,
  } = data;
  const status = projects.by_status;

  return (
    <>
      <Typography variant="h4" component="h1">Dashboard</Typography>
      <Typography sx={{ color: 'text.secondary', mb: 2 }}>
        {`As of ${formatDate(data.as_of)}`}
      </Typography>
      <TileGrid>
        <Tile label="Total projects" value={projects.total} to="/projects" />
        <Tile label="Active projects" value={status.Active} to="/projects?status=Active" />
        <Tile
          label="Completed projects"
          value={status.Completed}
          to="/projects?status=Completed"
        />
        <Tile
          label="On-hold projects"
          value={status['On Hold']}
          to="/projects?status=On+Hold"
        />
        <Tile label="Overdue projects" value={projects.overdue} />
        <Tile label="At-risk projects" value={projects.at_risk} />
        <Tile label="Upcoming deadlines" value={data.deadline_count} />
        <Tile
          label="Overdue deliverables"
          value={deliverables.overdue}
          to="/deliverables?overdue=true"
        />
      </TileGrid>
      <TileGrid>
        <Tile
          label="Deliverables completed"
          value={`${deliverables.completed} of ${deliverables.total}`}
        />
        <Tile label="Deliverables pending" value={deliverables.pending} />
        <Tile
          label="Deliverable completion"
          value={percent(deliverables.completion_percent)}
        />
        <Tile
          label="Resource utilization"
          value={percent(resources.utilization_percent)}
          to="/workload"
        />
        <Tile
          label="Over-allocated resources"
          value={`${resources.over_allocated} of ${resources.total}`}
          to="/resources?over_allocated=true"
        />
        <Tile label="Planned budget" value={formatMoney(budget.planned)} to="/budgets" />
        <Tile label="Actual expenditure" value={formatMoney(budget.actual)} to="/expenses" />
        <Tile label="Remaining budget" value={formatMoney(budget.remaining)} />
        <Tile label="Budget consumed" value={percent(budget.consumed_percent)} />
        <Tile
          label="Over-budget projects"
          value={budget.by_status['Over Budget']}
          to="/budgets?budget_status=Over+Budget"
        />
      </TileGrid>
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          mb: 2,
          gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(3, minmax(0, 1fr))' },
        }}
      >
        <CountBars
          title="Projects by status"
          counts={status}
          linkTo={projectsWith('status')}
        />
        <CountBars
          title="Open projects by risk"
          counts={projects.by_risk}
          linkTo={projectsWith('risk')}
        />
        <CountBars
          title="Deliverables by status"
          counts={deliverables.by_status}
          linkTo={(name) => `/deliverables?${new URLSearchParams({ status: name })}`}
        />
      </Box>
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          alignItems: 'start',
          gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' },
        }}
      >
        <RiskyProjects projects={data.risky_projects} total={projects.at_risk} />
        <Deadlines
          deadlines={data.deadlines}
          total={data.deadline_count}
          days={data.upcoming_days}
        />
      </Box>
    </>
  );
}

export default DashboardPage;
