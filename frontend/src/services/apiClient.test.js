import {
  describe, expect, it, vi,
} from 'vitest';
import { failure, json, mockApi } from '../test/helpers.jsx';
import {
  readTokens, request, setSessionEndedHandler, storeTokens,
} from './apiClient.js';

const expired = () => failure(401, 'token_expired', 'Expired');

describe('apiClient', () => {
  it('sends the token and skips empty parameters', async () => {
    storeTokens({ access: 'abc', refresh: 'r' });
    const calls = mockApi({ 'GET /projects': () => json({ items: [] }) });
    await request('/projects', { params: { search: '', status: ['A', 'B'], page: 0 } });
    expect(calls[0].token).toBe('Bearer abc');
    expect(calls[0].query.toString()).toBe('status=A&status=B&page=0');
  });

  it('refreshes once for requests that expire together', async () => {
    storeTokens({ access: 'old', refresh: 'r' });
    const calls = mockApi({
      'GET /projects': ({ token }) => (token === 'Bearer new' ? json('ok') : expired()),
      'POST /auth/refresh': () => json({ access_token: 'new' }),
    });
    const results = await Promise.all([request('/projects'), request('/projects')]);
    expect(results).toEqual(['ok', 'ok']);
    expect(calls.filter(({ key }) => key === 'POST /auth/refresh')).toHaveLength(1);
    expect(readTokens()).toEqual({ access: 'new', refresh: 'r' });
  });

  it('ends the session when the refresh is refused', async () => {
    const ended = vi.fn();
    setSessionEndedHandler(ended);
    storeTokens({ access: 'old', refresh: 'r' });
    mockApi({
      'GET /projects': expired,
      'POST /auth/refresh': () => failure(401, 'invalid_token', 'No'),
    });
    await expect(request('/projects')).rejects.toMatchObject({ status: 401 });
    expect(readTokens()).toBeNull();
    expect(ended).toHaveBeenCalledOnce();
  });

  it('keeps the session when access is denied', async () => {
    storeTokens({ access: 'a', refresh: 'r' });
    mockApi({ 'GET /users': () => failure(403, 'access_denied', 'Denied') });
    await expect(request('/users')).rejects.toMatchObject({ code: 'access_denied' });
    expect(readTokens()).not.toBeNull();
  });

  it('explains network failures and unexpected pages', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('offline'));
    await expect(request('/x')).rejects.toThrow('Cannot reach the server');
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response('<html></html>'));
    await expect(request('/x')).rejects.toMatchObject({ code: 'unexpected_response' });
  });

  it('maps server details to form fields', async () => {
    mockApi({
      'POST /projects': () => failure(400, 'validation_error', 'Bad', [
        { field: 'body.code', message: 'Wrong' }, { field: 'body', message: 'Dates' },
      ]),
    });
    const error = await request('/projects', { method: 'POST', body: {} }).catch((e) => e);
    expect(error.fieldErrors).toEqual({ code: 'Wrong', '': 'Dates' });
  });
});
