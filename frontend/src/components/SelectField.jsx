import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';

/**
 * A drop-down list.
 * @param {Object} props Component props; extra props go to the text field.
 * @returns {JSX.Element} The field.
 */
function SelectField({ options, emptyLabel = null, ...props }) {
  return (
    <TextField select fullWidth size="small" {...props}>
      {emptyLabel !== null && <MenuItem value="">{emptyLabel}</MenuItem>}
      {options.map((option) => {
        const { id, name } = typeof option === 'string' ? { id: option, name: option } : option;
        return <MenuItem key={id} value={id}>{name}</MenuItem>;
      })}
    </TextField>
  );
}

SelectField.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.shape({
        id: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
        name: PropTypes.string,
      }),
    ]),
  ).isRequired,
  emptyLabel: PropTypes.string,
};

export default SelectField;
