import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import { useEffect, useState } from 'react';
import useScreen from '../hooks/useScreen.js';

const SEARCH_DELAY_MS = 350;

/**
 * Search and filter controls for a list. On phones the filters are folded, so
 * the list stays in sight.
 * @param {Object} props Component props; children are the filters.
 * @returns {JSX.Element} The controls.
 */
function FilterPanel({
  search, onChange, onClear, children,
}) {
  const { isMobile } = useScreen();
  const [text, setText] = useState(search);
  const [open, setOpen] = useState(false);
  const showFilters = !isMobile || open;

  // Wait until typing pauses before searching.
  useEffect(() => {
    if (text === search) return undefined;
    const timer = setTimeout(() => onChange({ search: text }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text, search, onChange]);

  return (
    <Paper component="section" aria-label="Search and filters" sx={{ p: 2, mb: 2 }}>
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: {
            xs: 'minmax(0, 1fr)',
            sm: 'repeat(2, minmax(0, 1fr))',
            md: 'repeat(4, minmax(0, 1fr))',
          },
        }}
      >
        <TextField
          type="search"
          size="small"
          label="Search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          slotProps={{ htmlInput: { maxLength: 100 } }}
        />
        {isMobile && (
          <Button aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? 'Hide filters' : 'Show filters'}
          </Button>
        )}
        {showFilters && children}
        {showFilters && (
          <Button
            onClick={() => {
              setText('');
              onClear();
            }}
          >
            Clear filters
          </Button>
        )}
      </Box>
    </Paper>
  );
}

FilterPanel.propTypes = {
  search: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  children: PropTypes.node.isRequired,
};

export default FilterPanel;
