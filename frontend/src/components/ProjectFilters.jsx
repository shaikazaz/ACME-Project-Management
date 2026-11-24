import PropTypes from 'prop-types';
import DateField from './DateField.jsx';
import FilterPanel from './FilterPanel.jsx';
import SelectField from './SelectField.jsx';

/**
 * Search and filter controls for the project list.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The controls.
 */
function ProjectFilters({
  filters, options, onChange, onClear,
}) {
  const field = (name) => ({
    value: filters[name],
    onChange: (event) => onChange({ [name]: event.target.value }),
  });

  return (
    <FilterPanel search={filters.search} onChange={onChange} onClear={onClear}>
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
        label="Department"
        options={options.departments}
        emptyLabel="All departments"
        {...field('department_id')}
      />
      <SelectField
        label="Project manager"
        options={options.managers}
        emptyLabel="All managers"
        {...field('manager_id')}
      />
      {options.budget_statuses.length > 0 && (
        <SelectField
          label="Budget status"
          options={options.budget_statuses}
          emptyLabel="All budgets"
          {...field('budget_status')}
        />
      )}
      {options.risk_levels.length > 0 && (
        <SelectField
          label="Risk"
          options={options.risk_levels}
          emptyLabel="All risk levels"
          {...field('risk')}
        />
      )}
      <DateField label="Ends from" {...field('end_from')} />
      <DateField label="Ends until" {...field('end_to')} />
    </FilterPanel>
  );
}

ProjectFilters.propTypes = {
  filters: PropTypes.objectOf(PropTypes.string).isRequired,
  options: PropTypes.shape({
    statuses: PropTypes.arrayOf(PropTypes.string),
    priorities: PropTypes.arrayOf(PropTypes.string),
    budget_statuses: PropTypes.arrayOf(PropTypes.string),
    risk_levels: PropTypes.arrayOf(PropTypes.string),
    departments: PropTypes.arrayOf(PropTypes.object),
    managers: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
  onChange: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
};

export default ProjectFilters;
