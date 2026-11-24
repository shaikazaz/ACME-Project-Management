import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import { useCallback } from 'react';
import useForm from '../hooks/useForm.js';
import useLoad from '../hooks/useLoad.js';
import { getExpenseOptions } from '../services/budgetService.js';
import { validateExpense } from '../utils/expenseForm.js';
import { today } from '../utils/format.js';
import DateField from './DateField.jsx';
import { FormDialog } from './FormLayout.jsx';
import SelectField from './SelectField.jsx';

/**
 * Form to add or edit an expense.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function ExpenseDialog({ expense = null, onCancel, onSubmit }) {
  const form = useForm(
    {
      amount: expense?.amount ?? '',
      category_id: expense?.category.id ?? '',
      expense_date: expense?.expense_date ?? today(),
      description: expense?.description ?? '',
    },
    (values) => validateExpense(values, today()),
    (values) => onSubmit({
      ...values,
      amount: String(values.amount).trim(),
      description: values.description.trim(),
    }),
  );
  const options = useLoad(useCallback((signal) => getExpenseOptions(signal), []));
  const known = expense ? [expense.category] : [];
  const { field } = form;

  return (
    <FormDialog
      title={expense ? 'Edit expense' : 'New expense'}
      form={form}
      submitLabel="Save expense"
      onCancel={onCancel}
    >
      <TextField
        required
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
        {...field('amount', 'Amount (USD)')}
      />
      <SelectField
        required
        options={options.data?.categories ?? known}
        {...field('category_id', 'Category', {
          help: options.error?.message,
          disabled: !options.data,
        })}
      />
      <DateField required {...field('expense_date', 'Date')} />
      <TextField required multiline minRows={2} {...field('description', 'Description')} />
    </FormDialog>
  );
}

ExpenseDialog.propTypes = {
  expense: PropTypes.shape({
    amount: PropTypes.string,
    category: PropTypes.shape({ id: PropTypes.number }),
    expense_date: PropTypes.string,
    description: PropTypes.string,
  }),
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

export default ExpenseDialog;
