import { describe, expect, it } from 'vitest';
import { PROJECT } from '../test/helpers.jsx';
import { formatDate, formatMoney, today } from './format.js';
import {
  EMPTY_PROJECT, toFormValues, toRequest, validateProject,
} from './projectForm.js';

const VALID = { ...toFormValues(PROJECT) };
const check = (changes) => Object.keys(validateProject({ ...VALID, ...changes }, '2026-11-24'));

describe('formatting', () => {
  it('formats dates and money', () => {
    expect(formatDate('2026-01-01')).toBe('1 Jan 2026');
    expect(formatDate(null)).toBe('—');
    expect(formatMoney('1000.50')).toBe('$1,000.50');
    expect(formatMoney(null)).toBe('—');
    expect(today()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('project form', () => {
  it('accepts a valid project and converts it', () => {
    expect(check({})).toEqual([]);
    expect(toRequest(VALID)).toMatchObject({
      code: 'CRM-1',
      department_id: 5,
      manager_id: 7,
      planned_budget: '1000.50',
      actual_completion_date: null,
    });
    expect(toRequest({ ...VALID, manager_id: '' }).manager_id).toBeNull();
  });

  it('lists every missing field', () => {
    expect(Object.keys(validateProject(EMPTY_PROJECT, '2026-11-24')).sort())
      .toEqual(['code', 'department_id', 'end_date', 'name', 'start_date']);
  });

  it.each([
    [{ code: 'has space' }, 'code'],
    [{ name: '   ' }, 'name'],
    [{ end_date: '2025-01-01' }, 'end_date'],
    [{ planned_budget: '-1' }, 'planned_budget'],
    [{ planned_budget: '1.001' }, 'planned_budget'],
    [{ planned_budget: 'abc' }, 'planned_budget'],
    [{ status: 'Completed' }, 'actual_completion_date'],
    [{ status: 'Completed', actual_completion_date: '2026-11-25' }, 'actual_completion_date'],
    [{ status: 'Completed', actual_completion_date: '2025-12-31' }, 'actual_completion_date'],
  ])('rejects %o', (changes, field) => {
    expect(check(changes)).toEqual([field]);
  });

  it('drops the completion date when a project is reopened', () => {
    const reopened = { ...VALID, status: 'Active', actual_completion_date: '2026-05-01' };
    expect(toRequest(reopened).actual_completion_date).toBeNull();
  });
});
