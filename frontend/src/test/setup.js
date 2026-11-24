import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

// jsdom has no screen size, so behave like a desktop unless a test says otherwise.
window.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  addListener() {},
  removeListener() {},
  addEventListener() {},
  removeEventListener() {},
});
