import PropTypes from 'prop-types';
import FilterPanel from './FilterPanel.jsx';
import SelectField from './SelectField.jsx';

// The API filter is true or false; the list shows words.
const ALLOCATION = [
  { id: 'true', name: 'Over-allocated' }, { id: 'false', name: 'Within capacity' },
];

/**
 * Search and filter controls for the resource list.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The controls.
 */
function ResourceFilters({
  filters, options, onChange, onClear,
}) {
  const field = (name) => ({
    value: filters[name],
    onChange: (event) => onChange({ [name]: event.target.value }),
  });
  return (
    <FilterPanel search={filters.search} onChange={onChange} onClear={onClear}>
      <SelectField
        label="Department"
        options={options.departments}
        emptyLabel="All departments"
        {...field('department_id')}
      />
      <SelectField
        label="Availability"
        options={options.availability}
        emptyLabel="All"
        {...field('availability')}
      />
      <SelectField
        label="Skill"
        options={options.skills}
        emptyLabel="All skills"
        {...field('skill')}
      />
      <SelectField
        label="Allocation"
        options={ALLOCATION}
        emptyLabel="All"
        {...field('over_allocated')}
      />
    </FilterPanel>
  );
}

ResourceFilters.propTypes = {
  filters: PropTypes.objectOf(PropTypes.string).isRequired,
  options: PropTypes.shape({
    departments: PropTypes.arrayOf(PropTypes.object),
    availability: PropTypes.arrayOf(PropTypes.string),
    skills: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
  onChange: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
};

export default ResourceFilters;
