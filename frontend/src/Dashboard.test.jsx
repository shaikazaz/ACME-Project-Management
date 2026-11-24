import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import {
  ADMIN, failure, json, MEMBER, PROJECT, renderApp,
} from './test/helpers.jsx';

const RISK = {
  level: 'High',
  reasons: [
    { code: 'deadline_passed', severity: 'High', message: 'The deadline passed 3 days ago.' },
    { code: 'over_allocated', severity: 'Medium', message: 'Over-allocated people: Rita.' },
  ],
  expected_progress_percent: 100,
  forecast_end_date: '2026-12-31',
};
const DASHBOARD = {
  as_of: '2026-11-24',
  upcoming_days: 14,
  projects: {
    total: 12,
    by_status: {
      Planned: 1, Active: 5, 'On Hold': 2, Completed: 3, Cancelled: 1,
    },
    overdue: 4,
    by_risk: { High: 6, Medium: 1, Low: 1 },
    at_risk: 7,
  },
  deliverables: {
    total: 20,
    completed: 9,
    pending: 11,
    overdue: 8,
    by_status: {
      'Not Started': 2, 'In Progress': 4, Blocked: 5, Completed: 9,
    },
    completion_percent: 45,
  },
  resources: {
    total: 15,
    over_allocated: 10,
    needs_cover: 0,
    capacity_percent: 1000,
    peak_percent: 875,
    utilization_percent: 87.5,
  },
  budget: {
    planned: '100000.00',
    actual: '75000.00',
    remaining: '25000.00',
    consumed_percent: 75,
    by_status: {
      'On Track': 8, Warning: 1, 'Over Budget': 13, 'No Budget': 0,
    },
  },
  deadline_count: 21,
  deadlines: [
    {
      kind: 'Project', id: 10, name: 'CRM rollout', project_id: 10, project_code: 'CRM-1',
      due_date: '2026-11-24', days_left: 0,
    },
    {
      kind: 'Milestone', id: 30, name: 'Beta', project_id: 10, project_code: 'CRM-1',
      due_date: '2026-11-25', days_left: 1,
    },
    {
      kind: 'Deliverable', id: 20, name: 'Testing', project_id: 10, project_code: 'CRM-1',
      due_date: '2026-11-30', days_left: 6,
    },
  ],
  risky_projects: [{
    id: 10,
    code: 'CRM-1',
    name: 'CRM rollout',
    status: 'Active',
    manager: null,
    end_date: '2026-11-21',
    progress_percent: 40,
    risk: RISK,
  }],
};
const routes = { 'GET /dashboard': () => json(DASHBOARD) };
const tile = (label) => screen.getByText(label, { selector: 'dt, dt *' })
  .closest('dt').parentElement.querySelector('dd').textContent;

describe('dashboard', () => {
  it('shows every figure from the API', async () => {
    renderApp('/dashboard', { routes });
    await screen.findByText('As of 24 Nov 2026');
    const expected = {
      'Total projects': '12',
      'Active projects': '5',
      'Completed projects': '3',
      'On-hold projects': '2',
      'Overdue projects': '4',
      'At-risk projects': '7',
      'Upcoming deadlines': '21',
      'Overdue deliverables': '8',
      'Deliverables completed': '9 of 20',
      'Deliverables pending': '11',
      'Deliverable completion': '45%',
      'Resource utilization': '87.5%',
      'Over-allocated resources': '10 of 15',
      'Planned budget': '$100,000.00',
      'Actual expenditure': '$75,000.00',
      'Remaining budget': '$25,000.00',
      'Budget consumed': '75%',
      'Over-budget projects': '13',
    };
    const found = Object.fromEntries(Object.keys(expected).map((label) => [label, tile(label)]));
    expect(found).toEqual(expected);
  });

  it('explains risks and links to the records', async () => {
    renderApp('/dashboard', { routes });
    const risks = await screen.findByRole('region', { name: 'Projects at risk' });
    expect(within(risks).getByText('High risk')).toBeVisible();
    expect(within(risks).getByText('The deadline passed 3 days ago.')).toBeVisible();
    expect(within(risks).getByText('The 1 most urgent of 7')).toBeVisible();
    const links = within(screen.getByRole('region', { name: 'Upcoming deadlines' }))
      .getAllByRole('link').map((link) => link.getAttribute('href'));
    expect(links).toEqual(['/projects/10', '/projects/10?tab=milestones', '/deliverables/20']);
    const bars = screen.getByRole('list', { name: 'Deliverables by status' });
    expect(within(bars).getByRole('link', { name: 'In Progress' }))
      .toHaveAttribute('href', '/deliverables?status=In+Progress');
  });

  it('shows an empty dashboard without errors', async () => {
    renderApp('/dashboard', {
      routes: {
        'GET /dashboard': () => json({
          ...DASHBOARD,
          projects: { ...DASHBOARD.projects, at_risk: 0 },
          deliverables: { ...DASHBOARD.deliverables, completion_percent: null },
          budget: { ...DASHBOARD.budget, consumed_percent: null },
          risky_projects: [],
          deadlines: [],
          deadline_count: 0,
        }),
      },
    });
    expect(await screen.findByText('No project is at risk')).toBeVisible();
    expect(tile('Budget consumed')).toBe('—');
    expect(screen.getByText('Nothing is due.')).toBeVisible();
  });

  it('shows errors instead of old or invented figures', async () => {
    let broken = true;
    renderApp('/dashboard', {
      routes: {
        'GET /dashboard': () => (broken
          ? failure(503, 'service_unavailable', 'The database is currently unavailable.')
          : json(DASHBOARD)),
      },
    });
    expect(await screen.findByText(/database is currently unavailable/)).toBeVisible();
    expect(screen.queryByText('Total projects')).toBeNull();
    broken = false;
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Total projects')).toBeVisible();
  });

  it.each([[ADMIN, 'Dashboard'], [MEMBER, 'Projects']])(
    'opens the right first page',
    async (user, heading) => {
      renderApp('/', { user, routes });
      expect(await screen.findByRole('heading', { name: heading, level: 1 })).toBeVisible();
    },
  );

  it('refuses team members', async () => {
    renderApp('/dashboard', { user: MEMBER });
    expect(await screen.findByText(/do not have permission/)).toBeVisible();
  });
});

describe('project risk', () => {
  it('explains the risk of a project', async () => {
    renderApp('/projects/10', {
      routes: { 'GET /projects/10': () => json({ ...PROJECT, risk: RISK }) },
    });
    const reasons = await screen.findByRole('list', { name: 'Risk reasons' });
    expect(within(reasons).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText(/At the current pace it ends on 31 Dec 2026/)).toBeVisible();
  });

  it('filters by risk on the server', async () => {
    const calls = renderApp('/projects');
    expect(await screen.findByText('Low risk')).toBeVisible();
    await userEvent.click(screen.getByLabelText('Risk'));
    await userEvent.click(await screen.findByRole('option', { name: 'High' }));
    await waitFor(() => {
      const last = calls.filter(({ key }) => key === 'GET /projects').at(-1);
      expect(last.query.get('risk')).toBe('High');
    });
  });
});
