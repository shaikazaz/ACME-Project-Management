import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback } from 'react';
import useLoad from '../hooks/useLoad.js';
import { getDependencyChain } from '../services/deliverableService.js';
import { formatDate } from '../utils/format.js';
import { EmptyState, ErrorState, LoadingState } from './PageStates.jsx';
import RelatedDeliverable from './RelatedDeliverable.jsx';

const BORDERS = { Completed: 'success.main', Blocked: 'error.main', 'In Progress': 'primary.main' };

function ChainCard({ node, before, projectCode }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2, borderLeft: 6, borderLeftColor: BORDERS[node.effective_status] ?? 'grey.400',
      }}
    >
      <RelatedDeliverable
        item={node.deliverable}
        projectCode={projectCode}
        status={node.effective_status}
      />
      <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
        {node.due_date && (
          <Typography variant="caption">{`Due ${formatDate(node.due_date)}`}</Typography>
        )}
        {node.is_overdue && (
          <Chip size="small" color="error" variant="outlined" label="Overdue" />
        )}
      </Box>
      {before.length > 0 && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {`After: ${before.map(({ deliverable }) => deliverable.name).join(', ')}`}
        </Typography>
      )}
    </Paper>
  );
}

const nodeShape = PropTypes.shape({
  key: PropTypes.string.isRequired,
  deliverable: PropTypes.shape({ name: PropTypes.string.isRequired }).isRequired,
  effective_status: PropTypes.string.isRequired,
  is_overdue: PropTypes.bool,
  due_date: PropTypes.string,
  step: PropTypes.number.isRequired,
});

ChainCard.propTypes = {
  node: nodeShape.isRequired,
  before: PropTypes.arrayOf(nodeShape).isRequired,
  projectCode: PropTypes.string.isRequired,
};

/**
 * Shows a project's dependency chain, one column per step.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The chain.
 */
function DependencyChain({ projectId, projectCode }) {
  const { data, error, reload } = useLoad(useCallback(
    (signal) => getDependencyChain(projectId, signal),
    [projectId],
  ));

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading dependencies" />;
  if (data.nodes.length === 0) {
    return <EmptyState title="No deliverables yet" text="Add deliverables to see the chain." />;
  }

  const byKey = Object.fromEntries(data.nodes.map((node) => [node.key, node]));
  const steps = [...new Set(data.nodes.map(({ step }) => step))].sort((a, b) => a - b);
  return (
    <Box
      component="ol"
      aria-label="Dependency chain"
      sx={{
        listStyle: 'none',
        m: 0,
        p: 0,
        pb: 2,
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2,
        overflowX: 'auto',
      }}
    >
      {steps.map((step, index) => (
        <Box component="li" key={step} sx={{ flex: { md: '1 0 190px' } }}>
          <Typography variant="subtitle2" gutterBottom>
            {`Step ${step}${index < steps.length - 1 ? ' →' : ''}`}
          </Typography>
          <Box sx={{ display: 'grid', gap: 1 }}>
            {data.nodes.filter((node) => node.step === step).map((node) => (
              <ChainCard
                key={node.key}
                node={node}
                projectCode={projectCode}
                before={data.links
                  .filter(({ successor }) => successor === node.key)
                  .map(({ predecessor }) => byKey[predecessor])}
              />
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

DependencyChain.propTypes = {
  projectId: PropTypes.number.isRequired,
  projectCode: PropTypes.string.isRequired,
};

export default DependencyChain;
