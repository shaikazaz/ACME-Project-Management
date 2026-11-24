const BASE_URL = `${import.meta.env.VITE_API_URL ?? ''}/api/project-service`;
const TIMEOUT_MS = 30000;
const STORAGE_KEY = 'acme.session';

let onSessionEnded = () => {};
let refreshing = null;

/** An error returned by, or while contacting, the API. */
export class ApiError extends Error {
  /**
   * @param {string} message Message that is safe to show.
   * @param {{status?: number, code?: string, details?: Array}} [info] Details.
   */
  constructor(message, { status = 0, code = 'network_error', details = [] } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /**
   * Maps field names to messages, for display next to form fields.
   * @returns {Object<string, string>} Messages by field.
   */
  get fieldErrors() {
    return Object.fromEntries(
      this.details.map(({ field, message }) => [field.replace(/^body\.?/, ''), message]),
    );
  }
}

/**
 * Reads the tokens. They last until the tab closes, and survive a refresh.
 * @returns {{access: string, refresh: string}|null} The tokens, if signed in.
 */
export function readTokens() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

/**
 * Stores or clears the tokens.
 * @param {{access: string, refresh: string}|null} tokens The tokens.
 */
export function storeTokens(tokens) {
  if (tokens) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  } else {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}

/**
 * Registers what happens when the session ends unexpectedly.
 * @param {Function} handler Called without arguments.
 */
export function setSessionEndedHandler(handler) {
  onSessionEnded = handler;
}

function buildUrl(path, params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([name, value]) => {
    [value].flat().forEach((item) => {
      if (item !== undefined && item !== null && item !== '') query.append(name, item);
    });
  });
  const text = query.toString();
  return `${BASE_URL}${path}${text ? `?${text}` : ''}`;
}

async function send(path, { method = 'GET', body, params, signal, token } = {}) {
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  let text;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
    text = await response.text();
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError('Cannot reach the server. Check your connection and try again.');
  }

  if (response.status === 204) return null;
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    // A hosting error page instead of the API's JSON.
    throw new ApiError('The server sent an unexpected response.', {
      status: response.status,
      code: 'unexpected_response',
    });
  }
  if (!response.ok) {
    const { message, code, details } = data.error ?? {};
    throw new ApiError(message ?? 'Something went wrong. Please try again.', {
      status: response.status,
      code,
      details,
    });
  }
  return data;
}

async function refreshAccessToken() {
  const tokens = readTokens();
  const result = await send('/auth/refresh', {
    method: 'POST',
    body: { refresh_token: tokens?.refresh ?? '' },
  });
  storeTokens({ ...tokens, access: result.access_token });
  return result.access_token;
}

/**
 * Calls the API as the signed-in user, renewing an expired access token once.
 * @param {string} path Path below the service, such as "/projects".
 * @param {Object} [options] method, body, params and signal.
 * @returns {Promise<any>} The response data, or null when there is none.
 */
export async function request(path, options = {}) {
  try {
    const token = readTokens()?.access;
    return await send(path, { ...options, token }).catch(async (error) => {
      if (error.code !== 'token_expired') throw error;
      // Requests that expire together share one refresh.
      refreshing ??= refreshAccessToken().finally(() => {
        refreshing = null;
      });
      return send(path, { ...options, token: await refreshing });
    });
  } catch (error) {
    if (error.status === 401) {
      storeTokens(null);
      onSessionEnded();
    }
    throw error;
  }
}

/**
 * Calls a public endpoint, such as sign-in.
 * @param {string} path Path below the service.
 * @param {Object} [options] method, body, params and signal.
 * @returns {Promise<any>} The response data.
 */
export function publicRequest(path, options) {
  return send(path, options);
}
