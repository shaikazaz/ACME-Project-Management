import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import App from '../App.jsx';
import AuthProvider from '../context/AuthProvider.jsx';
import NotificationProvider from '../context/NotificationProvider.jsx';
import { storeTokens } from '../services/apiClient.js';

export const ADMIN = {
  id: 1,
  email: 'admin@example.com',
  full_name: 'Ada Admin',
  role: 'admin',
  permissions: [
    'projects:create', 'projects:delete', 'departments:manage', 'resources:view',
    'resources:manage', 'reports:view', 'budgets:manage', 'settings:manage',
    'users:manage',
  ],
};
export const MEMBER = {
  id: 2, email: 'm@example.com', full_name: 'Max Member', role: 'team_member', permissions: [],
};
export const OPTIONS = {
  statuses: ['Planned', 'Active', 'On Hold', 'Completed', 'Cancelled'],
  priorities: ['Low', 'Medium', 'High', 'Critical'],
  budget_statuses: ['On Track', 'Warning', 'Over Budget', 'No Budget'],
  risk_levels: ['High', 'Medium', 'Low'],
  departments: [{ id: 5, name: 'IT' }],
  managers: [{ id: 7, name: 'Mia Manager' }],
};
export const PROJECT = {
  id: 10,
  code: 'CRM-1',
  name: 'CRM rollout',
  description: 'Replace the CRM',
  department: { id: 5, name: 'IT' },
  manager: { id: 7, name: 'Mia Manager' },
  start_date: '2026-01-01',
  end_date: '2026-06-30',
  actual_completion_date: null,
  status: 'Planned',
  priority: 'High',
  progress_percent: 40,
  planned_budget: '1000.50',
  budget: {
    planned: '1000.50',
    actual: '250.25',
    remaining: '750.25',
    consumed_percent: 25,
    status: 'On Track',
  },
  risk: {
    level: 'Low', reasons: [], expected_progress_percent: 30, forecast_end_date: null,
  },
  can_edit: true,
  can_delete: true,
  deliverable_count: 3,
  deliverables_by_status: {
    'Not Started': 0, 'In Progress': 0, Blocked: 2, Completed: 1, Overdue: 1,
  },
  milestone_count: 1,
  assignment_count: 2,
  expense_count: 0,
  created_at: '2026-01-01T10:00:00Z',
  updated_at: '2026-01-02T10:00:00Z',
};

const RELATED = { id: 21, name: 'Development', project_code: 'CRM-1', status: 'In Progress' };
export const DELIVERABLE = {
  id: 20,
  name: 'Testing',
  description: 'Test it',
  project: { id: 10, code: 'CRM-1', name: 'CRM rollout' },
  milestone: null,
  owner: { id: 8, name: 'Olga Owner' },
  start_date: '2026-01-01',
  due_date: '2026-06-30',
  completion_date: null,
  status: 'Not Started',
  effective_status: 'Blocked',
  blocked_by: [RELATED],
  priority: 'High',
  progress_percent: 0,
  estimated_hours: 12.5,
  actual_hours: 0,
  is_overdue: true,
  days_overdue: 3,
  completed_late: false,
  can_edit: true,
  can_update: true,
  predecessors: [RELATED],
  successors: [],
};
export const DELIVERABLE_OPTIONS = {
  statuses: ['Not Started', 'In Progress', 'Blocked', 'Completed'],
  priorities: ['Low', 'Medium', 'High', 'Critical'],
  projects: [{ id: 10, name: 'CRM-1 · CRM rollout' }],
  owners: [{ id: 8, name: 'Olga Owner' }],
  milestones: [{ id: 30, name: 'Beta' }],
};

export const WORKLOAD = {
  capacity_percent: 100,
  current_percent: 70,
  peak_percent: 120,
  current_hours: 28,
  peak_hours: 48,
  capacity_hours: 40,
  utilization_percent: 120,
  remaining_percent: -20,
  is_over_allocated: true,
  is_over_allocated_now: false,
};
export const RESOURCE = {
  id: 40,
  employee_code: 'E1',
  full_name: 'Rita Resource',
  email: 'rita@example.com',
  department: { id: 5, name: 'IT' },
  job_title: 'Engineer',
  skills: ['Python', 'SQL'],
  availability: 'Available',
  user: null,
  workload: WORKLOAD,
  needs_cover: false,
  can_edit: true,
  updated_at: '2026-01-02T10:00:00Z',
  assignments: [
    {
      project_id: 10,
      project_name: 'CRM rollout',
      project_code: 'CRM-1',
      project_status: 'Active',
      project_role: 'Lead',
      allocation_percent: 70,
      start_date: '2026-01-01',
      end_date: '2026-06-30',
      counts: true,
    },
    {
      project_id: null,
      project_name: 'Another project',
      project_code: null,
      project_status: 'Active',
      project_role: '',
      allocation_percent: 50,
      start_date: '2026-05-01',
      end_date: '2026-06-30',
      counts: true,
    },
  ],
  periods: [{
    start_date: '2026-05-01', end_date: '2026-06-30', total_percent: 120, is_over_allocated: true,
  }],
};
export const RESOURCE_OPTIONS = {
  availability: ['Available', 'On Leave', 'Unavailable'],
  departments: [{ id: 5, name: 'IT' }],
  skills: ['Python', 'SQL'],
  users: [{ id: 2, name: 'Max Member (m@example.com)' }],
};

/** Builds a JSON response. */
export function json(body, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status });
}

/** Builds an API error response. */
export function failure(status, code, message, details = []) {
  return json({ error: { code, message, details } }, status);
}

/**
 * Replaces the network. Routes map "METHOD /path" to a function that receives
 * the request and returns a response. Returns the list of requests made.
 */
export function mockApi(routes) {
  const calls = [];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(input, 'http://localhost');
    const path = url.pathname.replace('/api/project-service', '');
    const call = {
      key: `${init.method} ${path}`,
      query: url.searchParams,
      body: init.body ? JSON.parse(init.body) : undefined,
      token: init.headers.Authorization,
    };
    calls.push(call);
    const route = routes[call.key];
    if (!route) throw new Error(`Unexpected request: ${call.key}`);
    return route(call);
  });
  return calls;
}

/** Renders the whole application as a signed-in user. */
export function renderApp(path, { user = ADMIN, routes = {}, signedIn = true } = {}) {
  if (signedIn) storeTokens({ access: 'access-1', refresh: 'refresh-1' });
  const calls = mockApi({
    'GET /auth/me': () => json(user),
    'GET /projects/options': () => json(OPTIONS),
    'GET /projects': () => json({ items: [PROJECT], total: 1 }),
    'GET /projects/10': () => json(PROJECT),
    'GET /resources': () => json({ items: [RESOURCE], total: 1 }),
    'GET /resources/options': () => json(RESOURCE_OPTIONS),
    'GET /resources/40': () => json(RESOURCE),
    'GET /deliverables': () => json({ items: [DELIVERABLE], total: 1 }),
    'GET /deliverables/options': () => json(DELIVERABLE_OPTIONS),
    'GET /deliverables/20': () => json(DELIVERABLE),
    ...routes,
  });
  render(
    <MemoryRouter initialEntries={[path]}>
      <NotificationProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </NotificationProvider>
    </MemoryRouter>,
  );
  return calls;
}
