import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import {
  failure, json, MEMBER, renderApp, RESOURCE, WORKLOAD,
} from './test/helpers.jsx';
import { toFormValues, validateAssignment, validateResource } from './utils/resourceForm.js';

const press = async (name) => userEvent.click(await screen.findByRole('button', { name }));
const sent = (calls, key) => calls.filter((call) => call.key === key);
const choose = async (label, option) => {
  await userEvent.click(screen.getByLabelText(label));
  await userEvent.click(await screen.findByRole('option', { name: option }));
};
const ok = {
  ...WORKLOAD, peak_percent: 80, utilization_percent: 80, is_over_allocated: false,
};

describe('resource checks', () => {
  it.each([
    [{}, []],
    [{ employee_code: 'a b' }, ['employee_code']],
    [{ email: 'nope' }, ['email']],
    [{ capacity_percent: '101' }, ['capacity_percent']],
    [{ capacity_percent: '-1' }, ['capacity_percent']],
    [{ department_id: '' }, ['department_id']],
    [{ skills: 'x'.repeat(51) }, ['skills']],
  ])('checks resource %o', (changes, fields) => {
    expect(Object.keys(validateResource({ ...toFormValues(RESOURCE), ...changes })))
      .toEqual(fields);
  });

  it.each([
    [{}, []],
    [{ allocation_percent: '0' }, ['allocation_percent']],
    [{ allocation_percent: '100.01' }, ['allocation_percent']],
    [{ allocation_percent: 'abc' }, ['allocation_percent']],
    [{ resource_id: '' }, ['resource_id']],
    [{ end_date: '2025-01-01' }, ['end_date']],
  ])('checks assignment %o', (changes, fields) => {
    const valid = {
      resource_id: 1, allocation_percent: '50', start_date: '2026-01-01', end_date: '2026-02-01',
    };
    expect(Object.keys(validateAssignment({ ...valid, ...changes }))).toEqual(fields);
  });
});

describe('resource list', () => {
  it('flags over-allocation and filters on the server', async () => {
    const calls = renderApp('/resources');
    const table = await screen.findByRole('table', { name: 'Resources' });
    expect(within(table).getByText('120% of 100%')).toBeVisible();
    expect(within(table).getByText('Over-allocated later')).toBeVisible();
    await choose('Allocation', 'Over-allocated');
    await choose('Skill', 'SQL');
    await waitFor(() => {
      const { query } = sent(calls, 'GET /resources').at(-1);
      expect([query.get('over_allocated'), query.get('skill')]).toEqual(['true', 'SQL']);
    });
  });

  it.each(['/resources', '/resources/40', '/resources/new', '/workload'])(
    'refuses %s without permission',
    async (path) => {
      renderApp(path, { user: MEMBER });
      expect(await screen.findByText(/do not have permission/)).toBeVisible();
      expect(screen.queryByRole('link', { name: 'Resources' })).toBeNull();
    },
  );
});

describe('resource details', () => {
  it('explains the load and hides other projects', async () => {
    renderApp('/resources/40');
    expect(await screen.findByText(/up to 120% is assigned, but the capacity is 100%/))
      .toBeVisible();
    expect(screen.getByRole('link', { name: 'CRM-1 · CRM rollout' })).toBeVisible();
    expect(screen.getByText('Another project')).toBeVisible();
    expect(screen.queryByRole('link', { name: /Another project/ })).toBeNull();
    expect(screen.getByText(/120% \(over capacity\)/)).toBeVisible();
  });

  it('shows why a person cannot be deleted', async () => {
    renderApp('/resources/40', {
      routes: {
        'DELETE /resources/40': () => failure(409, 'conflict', 'This person still has project assignments.'),
      },
    });
    await press('Delete');
    await press('Delete resource');
    expect(await screen.findByText(/still has project assignments/)).toBeVisible();
  });
});

describe('resource form', () => {
  it('creates a resource', async () => {
    const calls = renderApp('/resources/new', {
      routes: { 'POST /resources': () => json(RESOURCE, 201) },
    });
    await press('Create resource');
    expect(await screen.findByText('Enter a name')).toBeVisible();
    await userEvent.type(screen.getByLabelText(/Employee code/), 'E1');
    await userEvent.type(screen.getByLabelText(/Full name/), 'Rita');
    await userEvent.type(screen.getByLabelText(/^Email/), 'rita@example.com');
    await userEvent.type(screen.getByLabelText(/Job title/), 'Engineer');
    await userEvent.type(screen.getByLabelText(/Skills/), 'Python, SQL,');
    await choose(/^Department/, 'IT');
    await choose('Sign-in account', /Max Member/);
    await press('Create resource');
    expect(await screen.findByText('Resource created')).toBeVisible();
    expect(sent(calls, 'POST /resources')[0].body).toMatchObject({
      employee_code: 'E1',
      skills: ['Python', 'SQL'],
      capacity_percent: '100',
      department_id: 5,
      user_id: 2,
    });
  });

  it('keeps the linked account when editing', async () => {
    const user = { id: 9, name: 'Linked Person' };
    const calls = renderApp('/resources/40/edit', {
      routes: {
        'GET /resources/40': () => json({ ...RESOURCE, user }),
        'PUT /resources/40': () => json(RESOURCE),
      },
    });
    await press('Save changes');
    await screen.findByText('Resource updated');
    expect(sent(calls, 'PUT /resources/40')[0].body.user_id).toBe(9);
  });
});

describe('project team', () => {
  const assignment = {
    id: 50,
    resource: { id: 41, name: 'Sam Support' },
    job_title: 'Analyst',
    availability: 'Available',
    project_role: '',
    allocation_percent: 30,
    allocation_hours: 12,
    start_date: '2026-01-01',
    end_date: '2026-06-30',
    workload: ok,
  };
  const url = '/projects/10/assignments';
  const list = { [`GET ${url}`]: () => json({ items: [assignment], total: 1 }) };

  it('assigns a person and warns about over-allocation', async () => {
    const calls = renderApp('/projects/10?tab=team', {
      routes: {
        ...list,
        [`POST ${url}`]: () => json({
          ...assignment, resource: { id: 40, name: 'Rita Resource' }, workload: WORKLOAD,
        }, 201),
      },
    });
    expect(await screen.findByText(/30% \(12 h per week\)/)).toBeVisible();
    await press('Assign a person');
    await waitFor(() => expect(screen.getByLabelText(/Person/)).not.toHaveAttribute('aria-disabled'));
    await choose(/Person/, 'Rita Resource (120% of 100%)');
    await userEvent.type(screen.getByLabelText(/Allocation \(%\)/), '50');
    await press('Save assignment');
    expect(await screen.findByText('Rita Resource is over-allocated: 120% of 100% capacity.'))
      .toBeVisible();
    expect(sent(calls, `POST ${url}`)[0].body).toEqual({
      resource_id: 40,
      project_role: '',
      allocation_percent: '50',
      start_date: '2026-01-01',
      end_date: '2026-06-30',
    });
  });

  it('changes and removes an assignment', async () => {
    const calls = renderApp('/projects/10?tab=team', {
      routes: {
        ...list,
        [`PUT ${url}/50`]: () => json(assignment),
        [`DELETE ${url}/50`]: () => json(null, 204),
      },
    });
    await press('Change Sam Support');
    const percent = await screen.findByLabelText(/Allocation \(%\)/);
    await userEvent.clear(percent);
    await userEvent.type(percent, '25');
    await press('Save assignment');
    expect(await screen.findByText('Assignment saved')).toBeVisible();
    expect(sent(calls, `PUT ${url}/50`)[0].body).toMatchObject({
      resource_id: 41, allocation_percent: '25',
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await press('Remove Sam Support');
    await press('Remove person');
    expect(await screen.findByText('Assignment removed')).toBeVisible();
  });

  it('is hidden from team members', async () => {
    renderApp('/projects/10', { user: MEMBER });
    await screen.findByRole('tab', { name: 'Deliverables' });
    expect(screen.queryByRole('tab', { name: 'Team' })).toBeNull();
  });
});

describe('workload report', () => {
  it('shows the totals for the chosen period', async () => {
    const report = {
      period_from: '2026-01-01',
      period_to: null,
      resource_count: 5,
      over_allocated_count: 2,
      fully_allocated_count: 1,
      partly_allocated_count: 1,
      unallocated_count: 1,
      needs_cover_count: 0,
      utilization_percent: 56.6,
      departments: [{
        department: { id: 5, name: 'IT' },
        resource_count: 3,
        over_allocated_count: 2,
        utilization_percent: null,
      }],
    };
    const calls = renderApp('/workload', { routes: { 'GET /resources/workload': () => json(report) } });
    expect(await screen.findByText('56.6%')).toBeVisible();
    const table = screen.getByRole('table', { name: 'Workload by department' });
    expect(within(table).getByRole('row', { name: 'IT 3 2 —' })).toBeVisible();
    const first = sent(calls, 'GET /resources')[0].query;
    expect([first.get('sort'), first.get('order')]).toEqual(['utilization', 'desc']);
    await userEvent.type(screen.getByLabelText('Until'), '2026-03-31');
    await waitFor(() => {
      ['GET /resources/workload', 'GET /resources'].forEach((key) => {
        expect(sent(calls, key).at(-1).query.get('period_to')).toBe('2026-03-31');
      });
    });
  });
});
