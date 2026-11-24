import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { readTokens } from './services/apiClient.js';
import {
  ADMIN, failure, json, MEMBER, renderApp,
} from './test/helpers.jsx';
import { validateNewPassword, validateUser } from './utils/userForm.js';

const press = async (name) => userEvent.click(await screen.findByRole('button', { name }));
const sent = (calls, key) => calls.filter((call) => call.key === key);
const choose = async (label, option) => {
  await userEvent.click(screen.getByLabelText(label));
  await userEvent.click(await screen.findByRole('option', { name: option }));
};
const type = (label, text) => userEvent.type(screen.getByLabelText(label), text);
const closed = () => waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

const account = (values) => ({
  is_active: true, last_login_at: null, ...values,
});
const MAX = account({
  id: 2, full_name: 'Max Member', email: 'm@example.com', role: 'team_member',
});
const ME = account({
  id: ADMIN.id, full_name: ADMIN.full_name, email: ADMIN.email, role: 'admin',
});
const users = { 'GET /users': () => json({ items: [ME, MAX], total: 2 }) };

describe('account checks', () => {
  it.each([
    [{}, []],
    [{ full_name: ' ' }, ['full_name']],
    [{ email: 'nope' }, ['email']],
    [{ password: 'short' }, ['password']],
    [{ password: 'aaaaaaaaaaaaaa' }, ['password']],
  ])('checks %o', (changes, fields) => {
    const valid = { full_name: 'A', email: 'a@b.co', password: 'A perfectly fine one' };
    expect(Object.keys(validateUser({ ...valid, ...changes }, true))).toEqual(fields);
  });

  it('needs matching passwords', () => {
    const values = { new_password: 'A perfectly fine one', repeat: 'Another one' };
    expect(validateNewPassword(values)).toHaveProperty('repeat');
    expect(validateNewPassword({ ...values, repeat: values.new_password })).toEqual({});
  });
});

describe('user administration', () => {
  it('creates an account', async () => {
    const calls = renderApp('/admin/users', {
      routes: { ...users, 'POST /users': ({ body }) => json({ id: 9, ...body }, 201) },
    });
    await press('New account');
    await press('Save account');
    expect(await screen.findByText('Enter a name')).toBeVisible();
    await type(/Full name/, 'New Person');
    await type(/^Email/, 'new@example.com');
    await type(/^Password/, 'A perfectly fine one');
    const dialog = screen.getByRole('dialog');
    await userEvent.click(within(dialog).getByLabelText(/Role/));
    await userEvent.click(await screen.findByRole('option', { name: 'Project Manager' }));
    await press('Save account');
    expect(await screen.findByText('Account saved')).toBeVisible();
    expect(sent(calls, 'POST /users')[0].body).toEqual({
      full_name: 'New Person',
      email: 'new@example.com',
      role: 'project_manager',
      is_active: true,
      password: 'A perfectly fine one',
    });
  });

  it('shows a duplicate email next to the field', async () => {
    renderApp('/admin/users', {
      routes: {
        ...users,
        'PUT /users/2': () => failure(409, 'conflict', 'Email exists.', [
          { field: 'email', message: 'Email exists.' },
        ]),
      },
    });
    await press('Edit Max Member');
    await press('Save account');
    expect(await screen.findByLabelText(/^Email/)).toBeInvalid();
  });

  it('protects the own account and updates the own name', async () => {
    renderApp('/admin/users', {
      routes: { ...users, 'PUT /users/1': ({ body }) => json({ ...ME, ...body }) },
    });
    await screen.findByRole('table', { name: 'Accounts' });
    expect(screen.queryByRole('button', { name: `Delete ${ADMIN.full_name}` })).toBeNull();
    await press(`Edit ${ADMIN.full_name}`);
    expect(screen.getByRole('switch')).toBeDisabled();
    await userEvent.clear(screen.getByLabelText(/Full name/));
    await type(/Full name/, 'Ada Renamed');
    await press('Save account');
    await closed();
    await press('Menu');
    expect(await screen.findByText('Ada Renamed')).toBeVisible();
  });

  it('sets passwords and deletes accounts', async () => {
    const calls = renderApp('/admin/users', {
      routes: {
        ...users,
        'POST /users/2/reset-password': () => json(null, 204),
        'DELETE /users/2': () => failure(409, 'conflict', 'This user still manages projects.'),
      },
    });
    await press('Set password of Max Member');
    await type(/^New password/, 'A perfectly fine one');
    await type(/Repeat/, 'A perfectly fine one');
    await press('Save password');
    await closed();
    expect(sent(calls, 'POST /users/2/reset-password')[0].body)
      .toEqual({ new_password: 'A perfectly fine one' });
    await press('Delete Max Member');
    await press('Delete account');
    expect(await screen.findByText('This user still manages projects.')).toBeVisible();
  });

  it('filters on the server', async () => {
    const calls = renderApp('/admin/users', { routes: users });
    await screen.findByRole('table', { name: 'Accounts' });
    await choose('Role', 'Team Member');
    await choose('Status', 'Inactive');
    await waitFor(() => {
      const { query } = sent(calls, 'GET /users').at(-1);
      expect([query.get('role'), query.get('is_active')]).toEqual(['team_member', 'false']);
      expect(query.get('sort')).toBeNull();
    });
  });

  it.each(['/admin', '/admin/settings'])('refuses %s without permission', async (path) => {
    renderApp(path, { user: MEMBER });
    expect(await screen.findByText(/do not have permission/)).toBeVisible();
  });
});

describe('departments', () => {
  it('creates, edits and explains refused deletions', async () => {
    const calls = renderApp('/admin/departments', {
      routes: {
        'GET /departments': () => json({
          items: [{ id: 5, name: 'IT', description: 'Tech' }], total: 1,
        }),
        'POST /departments': () => json({ id: 6, name: 'Legal' }, 201),
        'PUT /departments/5': () => json({ id: 5, name: 'IT' }),
        'DELETE /departments/5': () => failure(409, 'conflict', 'The department is used by projects.'),
      },
    });
    await press('New department');
    await type(/Department name/, 'Legal');
    await press('Save department');
    await closed();
    expect(sent(calls, 'POST /departments')[0].body).toEqual({ name: 'Legal', description: '' });
    await press('Edit IT');
    await press('Save department');
    await closed();
    expect(sent(calls, 'PUT /departments/5')[0].body).toEqual({ name: 'IT', description: 'Tech' });
    await press('Delete IT');
    await press('Delete department');
    expect(await screen.findByText('The department is used by projects.')).toBeVisible();
  });
});

describe('settings', () => {
  it('checks and saves a setting', async () => {
    const calls = renderApp('/admin/settings', {
      routes: {
        'GET /settings': () => json({
          items: [{ key: 'lag', value: 15, description: 'Schedule lag' }], total: 1,
        }),
        'PUT /settings/lag': () => json({ key: 'lag', value: 20, description: 'Schedule lag' }),
      },
    });
    const input = await screen.findByLabelText('Schedule lag');
    expect(screen.getByRole('button', { name: 'Save Schedule lag' })).toBeDisabled();
    await userEvent.clear(input);
    await userEvent.type(input, '-1');
    await press('Save Schedule lag');
    expect(await screen.findByText('Enter a number of 0 or more')).toBeVisible();
    await userEvent.clear(input);
    await userEvent.type(input, '20');
    await press('Save Schedule lag');
    expect(await screen.findByText('Setting saved')).toBeVisible();
    expect(sent(calls, 'PUT /settings/lag')[0].body).toEqual({ value: '20' });
  });
});

describe('own password', () => {
  const open = async () => {
    await press('Menu');
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Change password' }));
    await type(/Current password/, 'old password');
    await type(/^New password/, 'A perfectly fine one');
    await type(/Repeat/, 'A perfectly fine one');
    await press('Save password');
  };

  it('changes and keeps this device signed in', async () => {
    renderApp('/projects', {
      routes: {
        'POST /auth/change-password': () => json({
          access_token: 'new-a', refresh_token: 'new-r', user: ADMIN,
        }),
      },
    });
    await open();
    expect(await screen.findByText(/Password changed/)).toBeVisible();
    expect(readTokens()).toEqual({ access: 'new-a', refresh: 'new-r' });
  });

  it('explains a wrong current password', async () => {
    renderApp('/projects', {
      routes: {
        'POST /auth/change-password': () => failure(400, 'bad_request', 'Your current password is incorrect.'),
      },
    });
    await open();
    expect(await screen.findByText('Your current password is incorrect.')).toBeVisible();
  });
});

describe('layout', () => {
  it('marks the current page and sets the title', async () => {
    renderApp('/deliverables/20');
    const link = await screen.findByRole('link', { name: 'Deliverables' });
    expect(link).toHaveAttribute('aria-current', 'page');
    await waitFor(() => expect(document.title).toBe('Deliverables · ACME Projects'));
  });

  it('shows a message when a page crashes', async () => {
    renderApp('/projects/10', {
      routes: { 'GET /projects/10': () => json({ id: 10 }) },
    });
    expect(await screen.findByText('This page could not be shown.')).toBeVisible();
  });
});
