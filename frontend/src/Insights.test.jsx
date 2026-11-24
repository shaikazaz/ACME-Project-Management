import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import {
  failure, json, MEMBER, PROJECT, renderApp,
} from './test/helpers.jsx';

const URL = '/projects/10?tab=insights';
const KEY = 'POST /projects/10/insights';
const RESULT = {
  source: 'ai',
  model: 'gemini-3.6-flash',
  notice: null,
  generated_at: '2026-11-24T10:00:00Z',
  risk_level: 'High',
  metrics: [{ label: 'Progress', value: '65%' }],
  unavailable: ['forecast end date'],
  insights: {
    summary: 'The project is on track.',
    deadline: ['It ends on 24 Dec 2026.'],
    budget: ['Spending is calm.'],
    resources: ['Nobody is over-allocated.'],
    deliverables: ['Testing is blocked.'],
    actions: [{ action: 'Finish Testing.', reason: 'It blocks the release.', priority: 'High' }],
  },
};
const RULES = {
  ...RESULT,
  source: 'rules',
  model: null,
  notice: { code: 'timeout', message: 'The AI service took too long.' },
  insights: { ...RESULT.insights, summary: 'Rules say so.' },
};
const press = async (name) => userEvent.click(await screen.findByRole('button', { name }));
const sent = (calls) => calls.filter(({ key }) => key === KEY);

describe('AI insights', () => {
  it('asks only when the user does, and shows every section', async () => {
    const calls = renderApp(URL, { routes: { [KEY]: () => json(RESULT) } });
    await screen.findByRole('button', { name: 'Generate AI Insights' });
    expect(sent(calls)).toHaveLength(0);
    await press('Generate AI Insights');
    expect(await screen.findByText('AI-generated')).toBeVisible();
    ['Summary', 'Deadline', 'Budget', 'Resources', 'Deliverables', 'Recommended actions',
      'Verified figures'].forEach((name) => {
      expect(screen.getByRole('region', { name })).toBeVisible();
    });
    expect(screen.getByText('The project is on track.')).toBeVisible();
    expect(screen.getByText(/Generated .*24 Nov 2026.* by gemini-3.6-flash/)).toBeVisible();
    const figures = screen.getByRole('region', { name: 'Verified figures' });
    expect(within(figures).getByText('65%')).toBeVisible();
    expect(screen.getByText('Unavailable: forecast end date.')).toBeVisible();
  });

  it('marks rule-based observations clearly', async () => {
    renderApp(URL, { routes: { [KEY]: () => json(RULES) } });
    await press('Generate AI Insights');
    expect(await screen.findByText('Rule-based, not AI')).toBeVisible();
    expect(screen.getByText('The AI service took too long.')).toBeVisible();
    expect(screen.queryByText('AI-generated')).toBeNull();
    expect(screen.queryByText(/gemini/)).toBeNull();
  });

  it('shows loading, then regenerates with fresh data', async () => {
    let release;
    let answer = new Promise((resolve) => { release = () => resolve(json(RESULT)); });
    const calls = renderApp(URL, { routes: { [KEY]: () => answer } });
    await press('Generate AI Insights');
    expect(await screen.findByLabelText('Generating insights')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Generating…' })).toBeDisabled();
    release();
    await screen.findByText('The project is on track.');
    answer = json(RULES);
    await press('Regenerate');
    expect(await screen.findByText('Rules say so.')).toBeVisible();
    expect(screen.queryByText('The project is on track.')).toBeNull();
    expect(sent(calls)).toHaveLength(2);
  });

  it('explains errors, lets the user retry and keeps the page working', async () => {
    let broken = true;
    renderApp(URL, {
      routes: {
        [KEY]: () => (broken ? failure(503, 'service_unavailable', 'Database is down.') : json(RESULT)),
      },
    });
    await press('Generate AI Insights');
    expect(await screen.findByText('Database is down.')).toBeVisible();
    broken = false;
    await press('Try again');
    expect(await screen.findByText('AI-generated')).toBeVisible();
    await userEvent.click(screen.getByRole('tab', { name: 'Overview' }));
    expect(await screen.findByText('Replace the CRM')).toBeVisible();
  });

  it('does not keep old insights when a new request fails', async () => {
    let broken = false;
    renderApp(URL, {
      routes: { [KEY]: () => (broken ? failure(500, 'server_error', 'Failed.') : json(RESULT)) },
    });
    await press('Generate AI Insights');
    await screen.findByText('AI-generated');
    broken = true;
    await press('Regenerate');
    expect(await screen.findByText('Failed.')).toBeVisible();
    expect(screen.queryByText('The project is on track.')).toBeNull();
  });

  it('shows text as text', async () => {
    const insights = { ...RESULT.insights, summary: '<img src=x onerror=alert(1)>' };
    renderApp(URL, { routes: { [KEY]: () => json({ ...RESULT, insights }) } });
    await press('Generate AI Insights');
    expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
  });

  it('is hidden from users who do not manage the project', async () => {
    renderApp(URL, {
      user: MEMBER,
      routes: {
        'GET /projects/10': () => json({
          ...PROJECT, planned_budget: null, budget: null, risk: null, can_edit: false,
        }),
      },
    });
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Overview' })).toBeVisible());
    expect(screen.queryByRole('tab', { name: 'AI Insights' })).toBeNull();
  });
});
