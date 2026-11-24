import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import PropTypes from 'prop-types';
import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import useLoad from '../hooks/useLoad.js';
import { listDeliverables } from '../services/deliverableService.js';
import DeliverableList from './DeliverableList.jsx';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';

const LIMIT = 100;

/**
 * The deliverables of one project that the user may view.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The section.
 */
function ProjectDeliverables({ project, canEdit }) {
  const { data, error, reload } = useLoad(useCallback(
    (signal) => listDeliverables({ project_id: project.id, limit: LIMIT }, signal),
    [project.id],
  ));
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading deliverables" />;

  const allLink = `/deliverables?project_id=${project.id}`;
  return (
    <>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2, alignItems: 'center' }}>
        {canEdit && (
          <Button
            variant="contained"
            component={Link}
            to={`/projects/${project.id}/deliverables/new`}
          >
            New deliverable
          </Button>
        )}
        {Object.entries(project.deliverables_by_status)
          .filter(([, count]) => count > 0)
          .map(([name, count]) => (
            <Chip key={name} size="small" variant="outlined" label={`${name}: ${count}`} />
          ))}
      </Box>
      {data.items.length === 0
        ? <EmptyState title="No deliverables to show" text="Deliverables you may view appear here." />
        : <DeliverableList deliverables={data.items} showProject={false} />}
      {data.total > LIMIT && (
        <Button component={Link} to={allLink}>{`Show all ${data.total}`}</Button>
      )}
    </>
  );
}

ProjectDeliverables.propTypes = {
  project: PropTypes.shape({
    id: PropTypes.number.isRequired,
    deliverables_by_status: PropTypes.objectOf(PropTypes.number).isRequired,
  }).isRequired,
  canEdit: PropTypes.bool.isRequired,
};

export default ProjectDeliverables;
