import { useState } from 'react';

/**
 * Handles the values, problems and submission of a form.
 * @param {Object} initialValues Initial values by field.
 * @param {function(Object): Object<string, string>} validate Returns messages
 *   by field; empty when valid.
 * @param {function(Object): Promise<any>} submit Sends the values. The form
 *   stays busy after success, because the caller leaves the page or dialog.
 * @returns {Object} values, formError, busy, change, field and handleSubmit.
 */
function useForm(initialValues, validate, submit) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  const change = (name, value) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
    setFormError('');
  };

  const field = (name, label, { help = '', disabled = false } = {}) => ({
    name,
    label,
    value: values[name],
    onChange: (event) => change(name, event.target.value),
    error: Boolean(errors[name]),
    helperText: errors[name] ?? help,
    disabled: busy || disabled,
    size: 'small',
    fullWidth: true,
  });

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const problems = validate(values);
    setErrors(problems);
    setFormError('');
    if (Object.keys(problems).length > 0) {
      setFormError('Please correct the highlighted fields.');
      return;
    }
    setBusy(true);
    try {
      await submit(values);
    } catch (failure) {
      const fieldErrors = failure.fieldErrors ?? {};
      setErrors(fieldErrors);
      setFormError(fieldErrors[''] ?? failure.message);
      setBusy(false);
    }
  };

  return {
    values, formError, busy, change, field, handleSubmit,
  };
}

export default useForm;
