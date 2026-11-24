import PropTypes from 'prop-types';
import useForm from '../hooks/useForm.js';
import { toProgressRequest, toProgressValues, validateProgress } from '../utils/deliverableForm.js';
import { today } from '../utils/format.js';
import { FormDialog } from './FormLayout.jsx';
import ProgressFields from './ProgressFields.jsx';

const STATUSES = ['Not Started', 'In Progress', 'Blocked', 'Completed'];

/**
 * Lets an owner update the progress of a deliverable.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The dialog.
 */
function ProgressDialog({ deliverable, onCancel, onSubmit }) {
  const form = useForm(
    toProgressValues(deliverable),
    (values) => validateProgress(values, today()),
    (values) => onSubmit(toProgressRequest(values)),
  );
  return (
    <FormDialog
      title="Update progress"
      form={form}
      submitLabel="Save progress"
      onCancel={onCancel}
    >
      <ProgressFields form={form} statuses={STATUSES} />
    </FormDialog>
  );
}

ProgressDialog.propTypes = {
  deliverable: PropTypes.shape({ status: PropTypes.string }).isRequired,
  onCancel: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
};

export default ProgressDialog;
