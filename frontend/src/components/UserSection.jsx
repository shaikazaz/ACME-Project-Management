import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import PropTypes from 'prop-types';
import { useCallback, useState } from 'react';
import { useAuth, useNotify } from '../context/contexts.js';
import useListParams from '../hooks/useListParams.js';
import useLoad from '../hooks/useLoad.js';
import {
  deleteUser, listUsers, resetPassword, saveUser,
} from '../services/adminService.js';
import { formatDateTime } from '../utils/format.js';
import { ROLES, roleName } from '../utils/userForm.js';
import ConfirmDialog from './ConfirmDialog.jsx';
import DataList from './DataList.jsx';
import FilterPanel from './FilterPanel.jsx';
import PagedResults from './PagedResults.jsx';
import PasswordDialog from './PasswordDialog.jsx';
import SelectField from './SelectField.jsx';
import UserDialog from './UserDialog.jsx';

const FILTERS = ['search', 'role', 'is_active'];
// The API filter is true or false; the list shows words.
const ACTIVITY = [{ id: 'true', name: 'Active' }, { id: 'false', name: 'Inactive' }];

function ActiveChip({ active }) {
  return (
    <Chip
      size="small"
      label={active ? 'Active' : 'Inactive'}
      color={active ? 'success' : 'default'}
    />
  );
}

ActiveChip.propTypes = { active: PropTypes.bool.isRequired };

/**
 * User administration.
 * @returns {JSX.Element} The section.
 */
function UserSection() {
  const { user: me, updateUser } = useAuth();
  const notify = useNotify();
  const list = useListParams(FILTERS, 'name');
  const { filters, page, requestParams } = list;
  // dialog: null, or { kind, user }.
  const [dialog, setDialog] = useState(null);
  const users = useLoad(useCallback((signal) => {
    // Accounts are always sorted by name.
    const params = { ...requestParams, sort: undefined, order: undefined };
    return listUsers(params, signal);
  }, [requestParams]));

  const field = (name) => ({
    value: filters[name],
    onChange: (event) => list.update({ [name]: event.target.value }),
  });
  const close = () => setDialog(null);
  const finish = (message) => {
    close();
    notify(message);
    users.reload();
  };
  const handleSave = async (values) => {
    const saved = await saveUser(values, dialog.user?.id);
    if (saved.id === me.id) updateUser(saved);
    finish('Account saved');
  };
  const handlePassword = async (values) => {
    await resetPassword(dialog.user.id, values.new_password);
    finish('Password set. The person has been signed out.');
  };
  const handleDelete = async () => {
    await deleteUser(dialog.user.id);
    finish('Account deleted');
  };

  const actions = (item) => (
    <Box sx={{ display: 'flex', flexWrap: 'wrap' }}>
      <Button
        size="small"
        aria-label={`Edit ${item.full_name}`}
        onClick={() => setDialog({ kind: 'edit', user: item })}
      >
        Edit
      </Button>
      <Button
        size="small"
        aria-label={`Set password of ${item.full_name}`}
        onClick={() => setDialog({ kind: 'password', user: item })}
      >
        Password
      </Button>
      {item.id !== me.id && (
        <Button
          size="small"
          color="error"
          aria-label={`Delete ${item.full_name}`}
          onClick={() => setDialog({ kind: 'delete', user: item })}
        >
          Delete
        </Button>
      )}
    </Box>
  );
  const columns = [
    { label: 'Name', render: (item) => item.full_name },
    { label: 'Email', render: (item) => item.email },
    { label: 'Role', render: (item) => roleName(item.role) },
    { label: 'Status', render: (item) => <ActiveChip active={item.is_active} /> },
    {
      label: 'Last sign-in',
      render: (item) => (item.last_login_at ? formatDateTime(item.last_login_at) : 'Never'),
    },
    { label: 'Actions', render: actions },
  ];
  const renderCard = (item) => (
    <>
      <Typography variant="h6" component="h3" sx={{ overflowWrap: 'anywhere' }}>
        {item.full_name}
      </Typography>
      <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{item.email}</Typography>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Typography variant="body2">{roleName(item.role)}</Typography>
        <ActiveChip active={item.is_active} />
      </Box>
      {actions(item)}
    </>
  );

  return (
    <>
      <Button
        variant="contained"
        sx={{ mb: 2 }}
        onClick={() => setDialog({ kind: 'edit', user: null })}
      >
        New account
      </Button>
      <FilterPanel search={filters.search} onChange={list.update} onClear={list.clear}>
        <SelectField label="Role" options={ROLES} emptyLabel="All roles" {...field('role')} />
        <SelectField
          label="Status"
          options={ACTIVITY}
          emptyLabel="All"
          {...field('is_active')}
        />
      </FilterPanel>
      <PagedResults
        result={users}
        page={page}
        onPage={list.setPage}
        emptyTitle="No accounts found"
        emptyText="Try different filters."
      >
        {(items) => (
          <DataList label="Accounts" rows={items} columns={columns} renderCard={renderCard} />
        )}
      </PagedResults>
      {dialog?.kind === 'edit' && (
        <UserDialog
          user={dialog.user}
          isSelf={dialog.user?.id === me.id}
          onCancel={close}
          onSubmit={handleSave}
        />
      )}
      {dialog?.kind === 'password' && (
        <PasswordDialog
          title={`Set password of ${dialog.user.full_name}`}
          onCancel={close}
          onSubmit={handlePassword}
        />
      )}
      {dialog?.kind === 'delete' && (
        <ConfirmDialog
          title="Delete this account?"
          text={`${dialog.user.full_name} (${dialog.user.email}) will be permanently deleted.`}
          confirmLabel="Delete account"
          onCancel={close}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

export default UserSection;
