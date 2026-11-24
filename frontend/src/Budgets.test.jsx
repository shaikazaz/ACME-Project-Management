import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import {
  failure, json, MEMBER, PROJECT, renderApp,
} from './test/helpers.jsx';
import { describeBudgetProblem, validateExpense } from './utils/expenseForm.js';
import { formatMoney } from './utils/format.js';

const press = async (name) => userEvent.click(await screen.findByRole('button', { name }));
const sent = (calls, key) => calls.filter((call) => call.key === key);
const choose = async (label, option) => {
  await userEvent.click(screen.getByLabelText(label));
  await userEvent.click(await screen.findByRole('option', { name: option }));
};

const EXAMPLE = {
  planned: '100000.00',
  actual: '75000.00',
  remaining: '25000.00',
  consumed_percent: 75,
  status: 'On Track',
};
const OVER = {
  planned: '100000.00',
  actual: '125000.00',
  remaining: '-25000.00',
  consumed_percent: 125,
  status: 'Over Budget',
};
const EXPENSE = {
  id: 60,
  project: { id: 10, code: 'CRM-1', name: 'CRM rollout' },
  category: { id: 3, name: 'Software' },
  amount: '25000.00',
  expense_date: '2026-03-10',
  description: 'Licences',
  created_by: { id: 1, name: 'Ada Admin' },
};
const CATEGORIES = [{ id: 3, name: 'Software' }, { id: 4, name: 'Travel' }];
const details = (budget) => ({
  ...budget,
  warning_percent: 80,
  expense_count: 1,
  categories: [{ category: CATEGORIES[0], amount: '75000.00', share_percent: 100 }],
  months: [{ month: '2026-03', amount: '75000.00' }],
});
const routes = (budget = EXAMPLE) => ({
  'GET /projects/10/budget': () => json(details(budget)),
  'GET /expenses': () => json({ items: [EXPENSE], total: 1, total_amount: '25000.00' }),
  'GET /expenses/options': () => json({
    categories: CATEGORIES, projects: [{ id: 10, name: 'CRM-1 · CRM rollout' }],
  }),
});
const tile = (label) => screen.getByText(label, { selector: 'dt' }).parentElement;

describe('budget helpers', () => {
  it('formats amounts without losing digits', () => {
    expect(formatMoney('75000.00')).toBe('$75,000.00');
    expect(formatMoney('-25000.00')).toBe('-$25,000.00');
    expect(formatMoney('999999999999.99')).toBe('$999,999,999,999.99');
  });

  it('explains budget problems', () => {
    expect(describeBudgetProblem(EXAMPLE, formatMoney)).toBe('');
    expect(describeBudgetProblem(OVER, formatMoney)).toBe('Over budget by $25,000.00.');
    const warning = { ...EXAMPLE, status: 'Warning', consumed_percent: 85 };
    expect(describeBudgetProblem(warning, formatMoney))
      .toBe('85% of the budget is used. $25,000.00 remains.');
  });

  it.each([
    [{}, []],
    [{ amount: '0' }, ['amount']],
    [{ amount: '0.00' }, ['amount']],
    [{ amount: '-5' }, ['amount']],
    [{ amount: '1.001' }, ['amount']],
    [{ amount: '1000000000000' }, ['amount']],
    [{ amount: '999999999999.99' }, []],
    [{ amount: '0.01' }, []],
    [{ category_id: '' }, ['category_id']],
    [{ expense_date: '2026-11-25' }, ['expense_date']],
    [{ expense_date: '' }, ['expense_date']],
    [{ description: '  ' }, ['description']],
  ])('checks expense %o', (changes, fields) => {
    const valid = {
      amount: '10', category_id: 3, expense_date: '2026-03-10', description: 'X',
    };
    expect(Object.keys(validateExpense({ ...valid, ...changes }, '2026-11-24'))).toEqual(fields);
  });
});

describe('project budget', () => {
  it('shows the workshop example', async () => {
    renderApp('/projects/10?tab=budget', { routes: routes() });
    await screen.findByText('Actual spending');
    expect(within(tile('Planned budget')).getByText('$100,000.00')).toBeVisible();
    expect(within(tile('Actual spending')).getByText('$75,000.00')).toBeVisible();
    expect(within(tile('Remaining')).getByText('$25,000.00')).toBeVisible();
    expect(within(tile('Consumed')).getByText('75%')).toBeVisible();
    expect(screen.queryByText(/Over budget by/)).toBeNull();
  });

  it('alerts when over budget', async () => {
    renderApp('/projects/10?tab=budget', { routes: routes(OVER) });
    expect(await screen.findByText('Over budget by $25,000.00.')).toBeVisible();
    expect(within(tile('Remaining')).getByText('-$25,000.00')).toBeVisible();
  });

  it('alerts on the overview too', async () => {
    renderApp('/projects/10', {
      routes: { 'GET /projects/10': () => json({ ...PROJECT, budget: OVER, risk: null }) },
    });
    expect(await screen.findByText('Over budget by $25,000.00.')).toBeVisible();
  });

  it('adds an expense and reloads the totals', async () => {
    let budget = EXAMPLE;
    const calls = renderApp('/projects/10?tab=budget', {
      routes: {
        ...routes(),
        'GET /projects/10/budget': () => json(details(budget)),
        'POST /projects/10/expenses': () => {
          budget = OVER;
          return json({ expense: EXPENSE, budget: OVER }, 201);
        },
      },
    });
    await press('New expense');
    await press('Save expense');
    expect(await screen.findByText('Choose a category')).toBeVisible();
    await userEvent.type(screen.getByLabelText(/Amount/), '50000.50');
    await choose(/Category/, 'Travel');
    await userEvent.type(screen.getByLabelText(/Description/), 'Flights');
    await press('Save expense');
    expect(await screen.findByText('Expense added. Over budget by $25,000.00.')).toBeVisible();
    expect(await screen.findByText('$125,000.00')).toBeVisible();
    expect(sent(calls, 'POST /projects/10/expenses')[0].body).toMatchObject({
      amount: '50000.50', category_id: 4, description: 'Flights',
    });
  });

  it('edits and deletes an expense', async () => {
    const calls = renderApp('/projects/10?tab=budget', {
      routes: {
        ...routes(),
        'PUT /expenses/60': () => json({ expense: EXPENSE, budget: EXAMPLE }),
        'DELETE /expenses/60': () => json(null, 204),
      },
    });
    await press('Edit Licences');
    const amount = await screen.findByLabelText(/Amount/);
    expect(amount).toHaveValue('25000.00');
    await userEvent.clear(amount);
    await userEvent.type(amount, '30000');
    await press('Save expense');
    expect(await screen.findByText('Expense saved.')).toBeVisible();
    expect(sent(calls, 'PUT /expenses/60')[0].body.amount).toBe('30000');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await press('Delete Licences');
    await press('Delete expense');
    expect(await screen.findByText('Expense deleted')).toBeVisible();
  });

  it('is hidden from users who may not see it', async () => {
    renderApp('/projects/10?tab=budget', {
      user: MEMBER,
      routes: {
        'GET /projects/10': () => json({
          ...PROJECT, planned_budget: null, budget: null, risk: null, can_edit: false,
        }),
      },
    });
    await screen.findByRole('tab', { name: 'Overview' });
    expect(screen.queryByRole('tab', { name: 'Budget' })).toBeNull();
    expect(screen.queryByText('Planned budget')).toBeNull();
  });
});

describe('budget list', () => {
  const page = {
    items: [{
      id: 10,
      code: 'CRM-1',
      name: 'CRM rollout',
      department: { id: 5, name: 'IT' },
      manager: null,
      project_status: 'Active',
      budget: OVER,
    }],
    total: 1,
    planned: '100000.00',
    actual: '125000.00',
    remaining: '-25000.00',
    consumed_percent: 125,
    by_status: {
      'On Track': 0, Warning: 0, 'Over Budget': 1, 'No Budget': 0,
    },
  };

  it('shows totals and filters on the server', async () => {
    const calls = renderApp('/budgets', { routes: { 'GET /budgets': () => json(page) } });
    const table = await screen.findByRole('table', { name: 'Budgets' });
    expect(within(table).getByText('Over Budget')).toBeVisible();
    expect(within(tile('Over budget')).getByText('1')).toBeVisible();
    const first = sent(calls, 'GET /budgets')[0].query;
    expect([first.get('sort'), first.get('order')]).toEqual(['consumed', 'desc']);
    await choose('Budget status', 'Over Budget');
    await waitFor(() => {
      expect(sent(calls, 'GET /budgets').at(-1).query.get('budget_status')).toBe('Over Budget');
    });
  });

  it.each(['/budgets', '/expenses'])('refuses %s without permission', async (path) => {
    renderApp(path, { user: MEMBER });
    expect(await screen.findByText(/do not have permission/)).toBeVisible();
  });
});

describe('expenses', () => {
  it('shows the total and filters on the server', async () => {
    const calls = renderApp('/expenses', { routes: routes() });
    expect(await screen.findByText('Total: $25,000.00')).toBeVisible();
    await choose('Category', 'Travel');
    await waitFor(() => {
      expect(sent(calls, 'GET /expenses').at(-1).query.get('category_id')).toBe('4');
    });
  });

  it('lets an admin manage categories', async () => {
    let refuse = true;
    const calls = renderApp('/expenses', {
      routes: {
        ...routes(),
        'GET /expense-categories': () => json({
          items: [{ id: 3, name: 'Software', expense_count: 1 },
            { id: 4, name: 'Travel', expense_count: 0 }],
          total: 2,
        }),
        'POST /expense-categories': () => (refuse
          ? failure(409, 'conflict', 'A category with this name already exists.')
          : json({ id: 9, name: 'Legal', expense_count: 0 }, 201)),
        'PUT /expense-categories/3': () => json({ id: 3, name: 'Apps', expense_count: 1 }),
        'DELETE /expense-categories/4': () => json(null, 204),
      },
    });
    await press('Categories');
    expect(await screen.findByRole('button', { name: 'Delete Software' })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('New category'), 'Travel');
    await press('Add category');
    expect(await screen.findByText(/already exists/)).toBeVisible();
    refuse = false;
    await press('Add category');
    await waitFor(() => expect(screen.getByLabelText('New category')).toHaveValue(''));
    await press('Rename Software');
    await userEvent.clear(screen.getByLabelText('New name for Software'));
    await userEvent.type(screen.getByLabelText('New name for Software'), 'Apps');
    await press('Rename category');
    await waitFor(() => {
      expect(sent(calls, 'PUT /expense-categories/3')[0]?.body).toEqual({ name: 'Apps' });
    });
    await press('Delete Travel');
    await waitFor(() => expect(sent(calls, 'DELETE /expense-categories/4')).toHaveLength(1));
  });
});
