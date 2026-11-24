import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useEffect, useRef, useState } from 'react';
import generateInsights from '../services/insightService.js';
import { formatDateTime } from '../utils/format.js';
import { Fact, FactList } from './Facts.jsx';
import { ErrorState } from './PageStates.jsx';
import { PriorityChip } from './ProjectChips.jsx';

const SECTIONS = [
  ['deadline', 'Deadline'],
  ['budget', 'Budget'],
  ['resources', 'Resources'],
  ['deliverables', 'Deliverables'],
];

function SourceChip({ source }) {
  return source === 'ai'
    ? <Chip size="small" color="primary" label="AI-generated" />
    : <Chip size="small" label="Rule-based, not AI" />;
}

SourceChip.propTypes = { source: PropTypes.oneOf(['ai', 'rules']).isRequired };

function Result({ result }) {
  const { insights, metrics, unavailable, notice } = result;
  return (
    <>
      {notice && <Alert severity="info" sx={{ mb: 2 }}>{notice.message}</Alert>}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', mb: 2 }}>
        <SourceChip source={result.source} />
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {`Generated ${formatDateTime(result.generated_at)}`
            + `${result.model ? ` by ${result.model}` : ''}`}
        </Typography>
      </Box>
      <Paper component="section" aria-label="Summary" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" component="h2">Summary</Typography>
        <Typography sx={{ overflowWrap: 'anywhere' }}>{insights.summary}</Typography>
      </Paper>
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          mb: 2,
          gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' },
        }}
      >
        {SECTIONS.map(([key, title]) => (
          <Paper key={key} component="section" aria-label={title} sx={{ p: 2 }}>
            <Typography variant="h6" component="h2">{title}</Typography>
            <Box component="ul" sx={{ m: 0, pl: 3, overflowWrap: 'anywhere' }}>
              {insights[key].map((text) => <li key={text}>{text}</li>)}
            </Box>
          </Paper>
        ))}
      </Box>
      <Paper component="section" aria-label="Recommended actions" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" component="h2">Recommended actions</Typography>
        <Box component="ol" sx={{ m: 0, pl: 3, overflowWrap: 'anywhere' }}>
          {insights.actions.map(({ action, reason, priority }) => (
            <Box component="li" key={`${action} ${reason}`} sx={{ py: 0.5 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
                <Typography component="span">{action}</Typography>
                <PriorityChip priority={priority} />
              </Box>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>{reason}</Typography>
            </Box>
          ))}
        </Box>
      </Paper>
      <Paper component="section" aria-label="Verified figures" sx={{ p: 2 }}>
        <Typography variant="h6" component="h2">Verified figures</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Calculated from the project records, never by AI.
        </Typography>
        <FactList>
          {metrics.map(({ label, value }) => <Fact key={label} label={label}>{value}</Fact>)}
        </FactList>
        {unavailable.length > 0 && (
          <Typography variant="body2" sx={{ mt: 2 }}>
            {`Unavailable: ${unavailable.join(', ')}.`}
          </Typography>
        )}
      </Paper>
    </>
  );
}

Result.propTypes = {
  result: PropTypes.shape({
    source: PropTypes.oneOf(['ai', 'rules']).isRequired,
    model: PropTypes.string,
    generated_at: PropTypes.string.isRequired,
    notice: PropTypes.shape({ message: PropTypes.string.isRequired }),
    insights: PropTypes.shape({
      summary: PropTypes.string.isRequired,
      actions: PropTypes.arrayOf(PropTypes.object).isRequired,
    }).isRequired,
    metrics: PropTypes.arrayOf(PropTypes.object).isRequired,
    unavailable: PropTypes.arrayOf(PropTypes.string).isRequired,
  }).isRequired,
};

/**
 * Explains a project on request. Nothing is generated until the user asks.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The section.
 */
function AiInsights({ projectId }) {
  const [state, setState] = useState({ busy: false, result: null, error: null });
  const controller = useRef(null);

  // Leaving the page cancels a running request.
  useEffect(() => () => controller.current?.abort(), []);

  const handleGenerate = async () => {
    const current = new AbortController();
    controller.current = current;
    setState(({ result }) => ({ busy: true, result, error: null }));
    try {
      const result = await generateInsights(projectId, current.signal);
      setState({ busy: false, result, error: null });
    } catch (error) {
      if (current.signal.aborted) return;
      // Old insights may no longer be true, so they are not kept.
      setState({ busy: false, result: null, error });
    }
  };

  const { busy, result, error } = state;
  const label = result ? 'Regenerate' : 'Generate AI Insights';
  return (
    <>
      <Typography sx={{ mb: 2 }}>
        Explains the latest project data and suggests what to do next. It changes nothing.
      </Typography>
      <Button variant="contained" onClick={handleGenerate} disabled={busy} sx={{ mb: 2 }}>
        {busy ? 'Generating…' : label}
      </Button>
      {busy && <LinearProgress aria-label="Generating insights" sx={{ mb: 2 }} />}
      {error && <ErrorState message={error.message} onRetry={handleGenerate} />}
      <Box aria-live="polite" aria-busy={busy} sx={{ opacity: busy ? 0.5 : 1 }}>
        {result && <Result result={result} />}
      </Box>
    </>
  );
}

AiInsights.propTypes = { projectId: PropTypes.number.isRequired };

export default AiInsights;
