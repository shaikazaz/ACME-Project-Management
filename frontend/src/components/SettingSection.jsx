import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import PropTypes from 'prop-types';
import { useState } from 'react';
import { useNotify } from '../context/contexts.js';
import useLoad from '../hooks/useLoad.js';
import { listSettings, saveSetting } from '../services/adminService.js';
import { ErrorState, LoadingState } from './PageStates.jsx';

function SettingField({ setting }) {
  const notify = useNotify();
  const [saved, setSaved] = useState(String(setting.value));
  const [value, setValue] = useState(saved);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    if (!/^\d{1,8}(\.\d{1,2})?$/.test(value.trim())) {
      setError('Enter a number of 0 or more');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await saveSetting(setting.key, value.trim());
      setSaved(String(result.value));
      setValue(String(result.value));
      notify('Setting saved');
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper component="form" noValidate onSubmit={handleSubmit} sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'start' }}>
        <TextField
          fullWidth
          size="small"
          label={setting.description}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setError('');
          }}
          error={Boolean(error)}
          helperText={error}
          disabled={busy}
          slotProps={{ htmlInput: { inputMode: 'decimal' } }}
        />
        <Button
          type="submit"
          variant="contained"
          disabled={busy || value.trim() === saved}
          aria-label={`Save ${setting.description}`}
        >
          Save
        </Button>
      </Box>
    </Paper>
  );
}

SettingField.propTypes = {
  setting: PropTypes.shape({
    key: PropTypes.string.isRequired,
    value: PropTypes.number.isRequired,
    description: PropTypes.string.isRequired,
  }).isRequired,
};

/**
 * Application settings, such as risk thresholds.
 * @returns {JSX.Element} The section.
 */
function SettingSection() {
  const { data, error, reload } = useLoad(listSettings);
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <LoadingState label="Loading settings" />;
  return (
    <Box sx={{ display: 'grid', gap: 2, maxWidth: 640 }}>
      {data.items.map((setting) => <SettingField key={setting.key} setting={setting} />)}
    </Box>
  );
}

export default SettingSection;
