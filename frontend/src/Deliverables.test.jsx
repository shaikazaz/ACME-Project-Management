import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import {
  DELIVERABLE, failure, json, MEMBER, PROJECT, renderApp,
} from './test/helpers.jsx';

const press = async (name) => userEvent.click(await screen.findByRole('button', { name }));
const sent = (calls, key) => calls.filter((call) => call.key === key);
const choose = async (label, option) => {
  await userEvent.click(screen.getByLabelText(label));
  await userEvent.click(await screen.findByRole('option', { name: option }));
};

describe('deliverable list', () => {
  it('shows blocked and overdue work with the reason', async () => {
    renderApp('/deliverables');
    const table = await screen.findByRole('table', { name: 'Deliverables' });
    ['Blocked', 'Overdue 3 days', 'Waiting for Development'].forEach((text) => {
      expect(within(table).getByText(text)).toBeVisible();
    });
  });

  it('filters on the server', async () => {
    const calls = renderApp('/deliverables');
    await screen.findByRole('table');
    await choose('Status', 'Blocked');
    await choose('Lateness', 'Overdue');
    await waitFor(() => {
      const { query } = sent(calls, 'GET /deliverables').at(-1);
      expect([query.get('status'), query.get('overdue')]).toEqual(['Blocked', 'true']);
    });
  });
});

describe('deliverable details', () => {
  it('explains why the work is blocked', async () => {
    renderApp('/deliverables/20');
    expect(await screen.findByText('Blocked. Waiting for Development.')).toBeVisible();
  });

  it('lets a team member update only the progress', async () => {
    const calls = renderApp('/deliverables/20', {
      user: MEMBER,
      routes: {
        'GET /deliverables/20': () => json({ ...DELIVERABLE, can_edit: false }),
        'PATCH /deliverables/20/progress': () => json(DELIVERABLE),
      },
    });
    await press('Update progress');
    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull();
    expect(screen.queryByLabelText('Add a predecessor')).toBeNull();
    await choose(/Status/, 'Completed');
    await press('Save progress');
    expect(await screen.findByText('Progress saved')).toBeVisible();
    expect(sent(calls, 'PATCH /deliverables/20/progress')[0].body).toEqual({
      status: 'Completed', progress_percent: '100', actual_hours: '0', completion_date: null,
    });
  });

  it('shows why the server refused to start blocked work', async () => {
    renderApp('/deliverables/20', {
      routes: {
        'PATCH /deliverables/20/progress': () => failure(
          409,
          'blocked',
          'Blocked: complete Development first.',
          [{ field: 'status', message: 'Blocked: complete Development first.' }],
        ),
      },
    });
    await press('Update progress');
    await choose(/Status/, 'In Progress');
    await press('Save progress');
    expect((await screen.findAllByText('Blocked: complete Development first.'))[0]).toBeVisible();
  });

  it('adds a dependency and explains a circular one', async () => {
    let circular = true;
    const calls = renderApp('/deliverables/20', {
      routes: {
        'GET /deliverables': () => json({
          items: [DELIVERABLE, { ...DELIVERABLE, id: 22, name: 'Deployment' }], total: 2,
        }),
        'POST /deliverables/20/predecessors': () => (circular
          ? failure(409, 'circular_dependency', 'This would create a circular dependency.')
          : json(DELIVERABLE, 201)),
      },
    });
    const pick = async () => {
      await userEvent.click(await screen.findByLabelText('Add a predecessor'));
      const options = await screen.findAllByRole('option');
      expect(options.map(({ textContent }) => textContent)).toEqual(['CRM-1 · Deployment']);
      await userEvent.click(options[0]);
      await press('Add');
    };
    await pick();
    expect(await screen.findByText('This would create a circular dependency.')).toBeVisible();
    circular = false;
    await press('Add');
    await waitFor(() => expect(sent(calls, 'GET /deliverables/20')).toHaveLength(2));
    expect(sent(calls, 'POST /deliverables/20/predecessors').at(-1).body)
      .toEqual({ predecessor_id: 22 });
  });

  it('removes a dependency', async () => {
    const calls = renderApp('/deliverables/20', {
      routes: { 'DELETE /deliverables/20/predecessors/21': () => json(null, 204) },
    });
    await press('Remove dependency on Development');
    await waitFor(() => expect(sent(calls, 'GET /deliverables/20')).toHaveLength(2));
  });

  it('keeps the delete dialog open when deletion is refused', async () => {
    renderApp('/deliverables/20', {
      routes: {
        'DELETE /deliverables/20': () => failure(409, 'conflict', 'Other deliverables depend on this one.'),
      },
    });
    await press('Delete');
    await press('Delete deliverable');
    expect(await screen.findByText('Other deliverables depend on this one.')).toBeVisible();
  });

  it('never links to hidden work', async () => {
    const hidden = {
      id: null, name: 'A deliverable in another project', project_code: null, status: 'Blocked',
    };
    renderApp('/deliverables/20', {
      routes: {
        'GET /deliverables/20': () => json({
          ...DELIVERABLE, predecessors: [hidden], blocked_by: [hidden],
        }),
      },
    });
    const list = await screen.findByRole('list', { name: 'Must be completed first' });
    expect(within(list).getByText(hidden.name)).toBeVisible();
    expect(within(list).queryByRole('link')).toBeNull();
    expect(within(list).queryByRole('button')).toBeNull();
  });
});

describe('deliverable form', () => {
  it('blocks invalid input, then creates', async () => {
    const calls = renderApp('/projects/10/deliverables/new', {
      routes: { 'POST /projects/10/deliverables': () => json(DELIVERABLE, 201) },
    });
    await press('Create deliverable');
    expect(await screen.findByText('Enter a name')).toBeVisible();
    await userEvent.type(screen.getByLabelText(/^Name/), 'Testing');
    await userEvent.type(screen.getByLabelText(/Start date/), '2026-01-01');
    await userEvent.type(screen.getByLabelText(/Due date/), '2025-01-01');
    await press('Create deliverable');
    expect(await screen.findByText('Due date must not be before the start date')).toBeVisible();
    await userEvent.clear(screen.getByLabelText(/Due date/));
    await userEvent.type(screen.getByLabelText(/Due date/), '2026-06-30');
    await choose('Owner', 'Olga Owner');
    await press('Create deliverable');
    expect(await screen.findByText('Deliverable created')).toBeVisible();
    expect(sent(calls, 'POST /projects/10/deliverables')[0].body).toMatchObject({
      name: 'Testing', owner_id: 8, milestone_id: null, completion_date: null,
    });
  });

  it('refuses users who do not manage the project', async () => {
    renderApp('/deliverables/20/edit', {
      user: MEMBER,
      routes: { 'GET /projects/10': () => json({ ...PROJECT, can_edit: false }) },
    });
    expect(await screen.findByText(/do not have permission/)).toBeVisible();
  });
});

describe('project sections', () => {
  const milestone = {
    id: 30,
    name: 'Beta',
    description: '',
    due_date: '2026-03-01',
    completed_date: null,
    is_overdue: true,
    deliverable_count: 2,
    completed_count: 1,
  };
  const node = (key, name, status, step) => ({
    key,
    deliverable: {
      id: step, name, project_code: 'CRM-1', status: 'Not Started',
    },
    effective_status: status,
    is_external: false,
    is_overdue: false,
    due_date: '2026-06-30',
    step,
  });

  it('shows the dependency chain in order', async () => {
    renderApp('/projects/10?tab=dependencies', {
      routes: {
        'GET /projects/10/dependencies': () => json({
          nodes: [node('a', 'Development', 'Not Started', 1), node('b', 'Testing', 'Blocked', 2)],
          links: [{ predecessor: 'a', successor: 'b' }],
        }),
      },
    });
    const chain = await screen.findByRole('list', { name: 'Dependency chain' });
    const steps = within(chain).getAllByRole('listitem');
    expect(within(steps[0]).getByText('Development')).toBeVisible();
    expect(within(steps[1]).getByText('After: Development')).toBeVisible();
    expect(within(steps[1]).getByText('Blocked')).toBeVisible();
  });

  it('manages milestones', async () => {
    const calls = renderApp('/projects/10?tab=milestones', {
      routes: {
        'GET /projects/10/milestones': () => json({ items: [milestone], total: 1 }),
        'POST /projects/10/milestones': () => json(milestone, 201),
        'PUT /projects/10/milestones/30': () => failure(409, 'conflict', 'No', [
          { field: 'completed_date', message: '1 of its deliverables are not completed.' },
        ]),
        'DELETE /projects/10/milestones/30': () => json(null, 204),
      },
    });
    expect(await screen.findByText(/1 of 2 deliverables completed/)).toBeVisible();
    await press('New milestone');
    await userEvent.type(screen.getByLabelText(/Milestone name/), 'GA');
    await userEvent.type(screen.getByLabelText(/Due date/), '2026-09-01');
    await press('Save milestone');
    expect(await screen.findByText('Milestone saved')).toBeVisible();
    expect(sent(calls, 'POST /projects/10/milestones')[0].body).toMatchObject({
      name: 'GA', completed_date: null,
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await press('Edit Beta');
    await press('Save milestone');
    expect(await screen.findByText(/deliverables are not completed/)).toBeVisible();
    await press('Cancel');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await press('Delete Beta');
    await press('Delete milestone');
    expect(await screen.findByText('Milestone deleted')).toBeVisible();
  });

  it('hides management from users who may not manage', async () => {
    renderApp('/projects/10?tab=deliverables', {
      user: MEMBER,
      routes: { 'GET /projects/10': () => json({ ...PROJECT, can_edit: false }) },
    });
    await screen.findByRole('table', { name: 'Deliverables' });
    expect(screen.queryByRole('link', { name: 'New deliverable' })).toBeNull();
    expect(screen.queryByRole('tab', { name: 'Dependencies' })).toBeNull();
  });
});
