/**
 * Checks an expense before it is sent. The server checks it again.
 * @param {Object} values The form values.
 * @param {string} latestDate The latest allowed date.
 * @returns {Object<string, string>} Messages by field; empty when valid.
 */
export function validateExpense(values, latestDate) {
  const errors = {};
  const amount = String(values.amount).trim();
  // Text checks only: numbers would round large amounts.
  if (!/^\d{1,12}(\.\d{1,2})?$/.test(amount) || /^[0.]+$/.test(amount)) {
    errors.amount = 'Enter an amount above 0, such as 250 or 250.50';
  }
  if (!values.category_id) errors.category_id = 'Choose a category';
  if (!values.expense_date) errors.expense_date = 'Choose a date';
  else if (values.expense_date > latestDate) {
    errors.expense_date = 'Expense date cannot be in the future';
  }
  if (!values.description.trim()) errors.description = 'Enter a description';
  else if (values.description.length > 2000) errors.description = 'Use up to 2000 characters';
  return errors;
}

/**
 * Explains a budget problem.
 * @param {Object} budget The budget.
 * @param {function(string): string} formatMoney Formats an amount.
 * @returns {string} The explanation, or an empty string.
 */
export function describeBudgetProblem(budget, formatMoney) {
  const { status, remaining, consumed_percent: consumed } = budget;
  if (status === 'Over Budget') {
    return `Over budget by ${formatMoney(remaining.replace('-', ''))}.`;
  }
  if (status === 'Warning') {
    return `${consumed}% of the budget is used. ${formatMoney(remaining)} remains.`;
  }
  return '';
}
