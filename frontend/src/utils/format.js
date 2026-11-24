const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

/**
 * Formats a "YYYY-MM-DD" date without shifting it between time zones.
 * @param {string|null} value The date.
 * @returns {string} The formatted date, or a dash.
 */
export function formatDate(value) {
  if (!value) return '—';
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Formats an amount of money. Text keeps every digit, where a number would be
 * rounded for very large amounts.
 * @param {string|number|null} value The amount.
 * @returns {string} The formatted amount, or a dash.
 */
export function formatMoney(value) {
  return value === null || value === undefined ? '—' : money.format(value);
}

/**
 * Formats a date and time in the viewer's time zone.
 * @param {string} value An ISO timestamp.
 * @returns {string} The formatted time.
 */
export function formatDateTime(value) {
  return new Date(value).toLocaleString('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

/**
 * Returns today's date in the viewer's time zone.
 * @returns {string} The date as "YYYY-MM-DD".
 */
export function today() {
  const now = new Date();
  const pad = (number) => String(number).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
