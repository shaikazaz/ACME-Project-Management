import PropTypes from 'prop-types';
import DateField from './DateField.jsx';
import FilterPanel from './FilterPanel.jsx';
import SelectField from './SelectField.jsx';

// The API filter is true or false; the list shows words.
const LATENESS = [{ id: 'true', name: 'Overdue' }, { id: 'false', name: 'Not overdue' }];

/**
 * Search and filter controls for the deliverable list.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The controls.
 */
function DeliverableFilters({
  filters, options, onChange, onClear,
}) {
  const field = (name) => ({
    value: filters[name],
    onChange: (event) => onChange({ [name]: event.target.value }),
  });

  return (
    <FilterPanel search={filters.search} onChange={onChange} onClear={onClear}>
      <SelectField
        label="Project"
        options={options.projects}
        emptyLabel="All projects"
        {...field('project_id')}
      />
      <SelectField
        label="Status"
        options={options.statuses}
        emptyLabel="All statuses"
        {...field('status')}
      />
      <SelectField
        label="Priority"
        options={options.priorities}
        emptyLabel="All priorities"
        {...field('priority')}
      />
      <SelectField
        label="Owner"
        options={options.owners}
        emptyLabel="All owners"
        {...field('owner_id')}
      />
      <SelectField
        label="Lateness"
        options={LATENESS}
        emptyLabel="All"
        {...field('overdue')}
      />
      <DateField label="Due until" {...field('due_to')} />
    </FilterPanel>
  );
}

DeliverableFilters.propTypes = {
  filters: PropTypes.objectOf(PropTypes.string).isRequired,
  options: PropTypes.shape({
    statuses: PropTypes.arrayOf(PropTypes.string),
    priorities: PropTypes.arrayOf(PropTypes.string),
    projects: PropTypes.arrayOf(PropTypes.object),
    owners: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
  onChange: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
};

export default DeliverableFilters;
