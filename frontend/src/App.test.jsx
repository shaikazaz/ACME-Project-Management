import {
  cleanup, screen, waitFor, within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  describe, expect, it, vi,
} from 'vitest';
import { readTokens } from './services/apiClient.js';
import {
  ADMIN, failure, json, MEMBER, PROJECT, renderApp,
} from './test/helpers.jsx';

const type = (label, text) => userEvent.type(screen.getByLabelText(label), text);
const press = (name) => userEvent.click(screen.getByRole('button', { name }));
const sent = (calls, key) => calls.filter((call) => call.key === key);

describe('signing in', () => {
  it('sends visitors to sign in, then back to the page they wanted', async () => {
    renderApp('/projects/10', {
      signedIn: false,
      routes: {
        'POST /auth/login': () => json({
          access_token: 'a', refresh_token: 'r', user: ADMIN,
        }),
      },
    });
    await type('Email', 'admin@example.com');
    await type('Password', 'secret');
    await press('Sign in');
    expect(await screen.findByRole('heading', { name: 'CRM rollout' })).toBeVisible();
  });

  it('shows why sign-in failed', async () => {
    renderApp('/login', {
      signedIn: false,
      routes: {
        'POST /auth/login': () => failure(401, 'invalid_credentials', 'Email or password is incorrect.'),
      },
    });
    await type('Email', 'a@b.co');
    await type('Password', 'wrong');
    await press('Sign in');
    expect(await screen.findByText('Email or password is incorrect.')).toBeVisible();
    expect(readTokens()).toBeNull();
  });

  it('offers demo accounts only when they are configured', async () => {
    renderApp('/login', { signedIn: false });
    expect(screen.queryByText(/Demo accounts/)).toBeNull();
    cleanup();
    vi.stubEnv('VITE_DEMO_ACCOUNTS', JSON.stringify([
      { label: 'Admin', email: 'admin@acme.test', password: 'demo password' },
    ]));
    const calls = renderApp('/login', {
      signedIn: false,
      routes: {
        'POST /auth/login': () => json({ access_token: 'a', refresh_token: 'r', user: MEMBER }),
      },
    });
    await press('Sign in as Admin');
    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeVisible();
    expect(sent(calls, 'POST /auth/login')[0].body)
      .toEqual({ email: 'admin@acme.test', password: 'demo password' });
    vi.unstubAllEnvs();
  });

  it('signs out on the server and here', async () => {
    const calls = renderApp('/projects', {
      routes: { 'POST /auth/logout': () => json(null, 204) },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Menu' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Sign out' }));
    expect(await screen.findByLabelText('Password')).toBeVisible();
    expect(sent(calls, 'POST /auth/logout')).toHaveLength(1);
    expect(readTokens()).toBeNull();
  });

  it('keeps the session when the server is unreachable at startup', async () => {
    renderApp('/projects', {
      routes: { 'GET /auth/me': () => { throw new TypeError('offline'); } },
    });
    expect(await screen.findByText('Cannot reach the server.')).toBeVisible();
    expect(readTokens()).not.toBeNull();
  });

  it('returns to sign-in when the session has ended', async () => {
    renderApp('/projects', {
      routes: { 'GET /auth/me': () => failure(401, 'invalid_token', 'No') },
    });
    expect(await screen.findByLabelText('Password')).toBeVisible();
  });
});

describe('project list', () => {
  it('shows projects from the API', async () => {
    renderApp('/projects');
    const table = await screen.findByRole('table', { name: 'Projects' });
    expect(within(table).getByRole('link', { name: 'CRM rollout' })).toBeVisible();
    expect(within(table).getByText('$1,000.50')).toBeVisible();
  });

  it('searches, filters and sorts on the server', async () => {
    const calls = renderApp('/projects');
    await screen.findByRole('table');
    await type('Search', 'crm');
    await waitFor(() => expect(sent(calls, 'GET /projects').at(-1).query.get('search')).toBe('crm'));
    await userEvent.click(screen.getByLabelText('Status'));
    await userEvent.click(await screen.findByRole('option', { name: 'Active' }));
    await waitFor(() => expect(sent(calls, 'GET /projects').at(-1).query.get('status')).toBe('Active'));
    await userEvent.click(screen.getByRole('button', { name: 'Project' }));
    await waitFor(() => {
      const { query } = sent(calls, 'GET /projects').at(-1);
      expect([query.get('sort'), query.get('search')]).toEqual(['name', 'crm']);
    });
    await press('Clear filters');
    await waitFor(() => expect(sent(calls, 'GET /projects').at(-1).query.get('status')).toBeNull());
  });

  it('restores filters from the address', async () => {
    const calls = renderApp('/projects?status=Active&page=2');
    await screen.findByRole('table');
    const { query } = sent(calls, 'GET /projects')[0];
    expect([query.get('status'), query.get('offset')]).toEqual(['Active', '20']);
  });

  it('shows empty and error states', async () => {
    let broken = true;
    renderApp('/projects', {
      routes: {
        'GET /projects': () => (broken
          ? failure(503, 'service_unavailable', 'The database is currently unavailable.')
          : json({ items: [], total: 0 })),
      },
    });
    expect(await screen.findByText(/database is currently unavailable/)).toBeVisible();
    broken = false;
    await press('Try again');
    expect(await screen.findByText('No projects found')).toBeVisible();
  });

  it('hides creation from users who may not create', async () => {
    renderApp('/projects', { user: MEMBER });
    await screen.findByRole('table');
    expect(screen.queryByRole('link', { name: 'New project' })).toBeNull();
  });
});

describe('clearing filters', () => {
  it('does not bring an old search back', async () => {
    const calls = renderApp('/projects?search=crm');
    await screen.findByRole('table');
    await press('Clear filters');
    await waitFor(() => expect(sent(calls, 'GET /projects').at(-1).query.get('search')).toBeNull());
    // Longer than the search delay.
    await new Promise((resolve) => { setTimeout(resolve, 600); });
    expect(sent(calls, 'GET /projects').at(-1).query.get('search')).toBeNull();
    expect(screen.getByLabelText('Search')).toHaveValue('');
  });
});

describe('project form', () => {
  it('blocks invalid input before sending', async () => {
    const calls = renderApp('/projects/new');
    await userEvent.click(await screen.findByRole('button', { name: 'Create project' }));
    expect(await screen.findByText('Enter a project code')).toBeVisible();
    expect(sent(calls, 'POST /projects')).toHaveLength(0);
    await type(/Project code/, 'A');
    expect(screen.queryByText('Enter a project code')).toBeNull();
    expect(screen.queryByText(/correct the highlighted/)).toBeNull();
  });

  it('shows server problems next to the field', async () => {
    renderApp('/projects/10/edit', {
      routes: {
        'PUT /projects/10': () => failure(409, 'conflict', 'Code exists.', [
          { field: 'code', message: 'Code exists.' },
        ]),
      },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Save changes' }));
    expect(await screen.findByLabelText(/Project code/)).toBeInvalid();
  });

  it('saves changes and opens the project', async () => {
    const calls = renderApp('/projects/10/edit', {
      routes: { 'PUT /projects/10': ({ body }) => json({ ...PROJECT, ...body }) },
    });
    const name = await screen.findByLabelText(/Project name/);
    await userEvent.clear(name);
    await userEvent.type(name, 'Renamed');
    await press('Save changes');
    expect(await screen.findByText('Project updated')).toBeVisible();
    expect(sent(calls, 'PUT /projects/10')[0].body).toMatchObject({
      name: 'Renamed', department_id: 5, manager_id: 7, planned_budget: '1000.50',
    });
  });

  it('adds a department while creating', async () => {
    renderApp('/projects/new', {
      routes: { 'POST /departments': ({ body }) => json({ id: 9, ...body }, 201) },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'New department' }));
    await type('Department name', 'Legal');
    await press('Add department');
    expect(await screen.findByText('Legal')).toBeVisible();
  });

  it.each([
    ['/projects/new', MEMBER, {}],
    ['/projects/10/edit', MEMBER, { 'GET /projects/10': () => json({ ...PROJECT, can_edit: false }) }],
  ])('refuses %s without permission', async (path, user, routes) => {
    renderApp(path, { user, routes });
    expect(await screen.findByText(/do not have permission/)).toBeVisible();
  });
});

describe('project details', () => {
  it('requires the project code before deleting', async () => {
    const calls = renderApp('/projects/10', {
      routes: { 'DELETE /projects/10': () => json(null, 204) },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    const confirm = screen.getByRole('button', { name: 'Delete project' });
    expect(confirm).toBeDisabled();
    await type('Type CRM-1 to confirm', 'crm-1');
    await userEvent.click(confirm);
    expect(await screen.findByText('Deleted CRM rollout')).toBeVisible();
    expect(sent(calls, 'DELETE /projects/10')[0].query.get('confirm_code')).toBe('crm-1');
  });

  it('hides budget and actions the user may not use', async () => {
    renderApp('/projects/10', {
      user: MEMBER,
      routes: {
        'GET /projects/10': () => json({
          ...PROJECT,
          planned_budget: null,
          budget: null,
          risk: null,
          can_edit: false,
          can_delete: false,
        }),
      },
    });
    await screen.findByRole('heading', { name: 'CRM rollout' });
    expect(screen.queryByText('Planned budget')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('explains a missing project', async () => {
    renderApp('/projects/99', {
      routes: { 'GET /projects/99': () => failure(404, 'not_found', 'Project not found.') },
    });
    expect(await screen.findByText(/does not exist, or you may not view it/)).toBeVisible();
  });
});
