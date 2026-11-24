import TextField from '@mui/material/TextField';

/**
 * A date input whose label never overlaps the browser's date hint.
 * @param {Object} props Text field props.
 * @returns {JSX.Element} The field.
 */
function DateField(props) {
  return (
    <TextField
      type="date"
      size="small"
      slotProps={{ inputLabel: { shrink: true } }}
      {...props}
    />
  );
}

export default DateField;
