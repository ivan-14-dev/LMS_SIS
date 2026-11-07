import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { patchApi, postApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';

const can = (capabilities, permission) => Boolean(
  capabilities?.permissions?.includes('*')
  || (capabilities?.permissions?.includes(permission)
    && !Object.keys(capabilities?.attributes?.permission_scopes?.[permission] || {}).length),
);
const denied = error => [401, 403].includes(error?.response?.status);
const ids = items => (Array.isArray(items) ? items.map(item => (typeof item === 'object' ? item.id : item)) : null);

const InstitutionalGroupsEditor = ({ variant, capabilities }) => {
  const groupsUrl = resourceUrl(variant, 'utilisateurs/groupes');
  const permissionsUrl = resourceUrl(variant, 'utilisateurs/permissions');
  const usersUrl = resourceUrl(variant, 'utilisateurs/comptes');
  const client = useQueryClient();
  const [selectedId, setSelectedId] = useState(null);
  const [name, setName] = useState('');
  const [permissionIds, setPermissionIds] = useState([]);
  const [userId, setUserId] = useState('');
  const [notice, setNotice] = useState('');
  const [selectionError, setSelectionError] = useState('');
  const canView = can(capabilities, 'auth.view_group');
  const canAdd = can(capabilities, 'auth.add_group');
  const canChange = can(capabilities, 'auth.change_group');
  const canAssign = canChange && can(capabilities, 'utilisateurs.change_utilisateur')
    && can(capabilities, 'utilisateurs.view_utilisateur');
  const groups = useQuery({
    queryKey: ['institutional-groups', groupsUrl],
    queryFn: () => fetchAllResourcePages(groupsUrl),
    enabled: canView,
  });
  const permissions = useQuery({
    queryKey: ['institutional-permissions', permissionsUrl],
    queryFn: () => fetchAllResourcePages(permissionsUrl),
    enabled: canView,
  });
  const users = useQuery({
    queryKey: ['institutional-group-users', usersUrl],
    queryFn: () => fetchAllResourcePages(usersUrl),
    enabled: canView && canAssign && selectedId !== null && selectedId !== 'new',
  });
  const group = groups.data?.find(item => item.id === selectedId);
  const selectedUser = users.data?.find(item => String(item.id) === String(userId));
  const membership = ids(selectedUser?.groups);
  const member = membership?.some(id => String(id) === String(selectedId));
  const save = useMutation({
    mutationFn: payload => (selectedId === 'new'
      ? postApi(groupsUrl, payload) : patchApi(`${groupsUrl}${selectedId}/`, payload)),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['institutional-groups', groupsUrl] });
      setSelectedId(null);
      setNotice('Groupe enregistré.');
    },
  });
  const assign = useMutation({
    mutationFn: add => postApi(
      `${groupsUrl}${selectedId}/${add ? 'assign' : 'unassign'}/`,
      { user_id: Number(userId) },
    ),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['institutional-group-users', usersUrl] });
      setNotice('Affectation du compte enregistrée.');
    },
  });

  if (!capabilities) { return <Alert severity="warning">Chargement des autorisations…</Alert>; }
  if (!canView) {
    return <Alert severity="warning">Accès non autorisé : permission de consultation des groupes requise.</Alert>;
  }
  if (groups.isPending || permissions.isPending) {
    return <Typography role="status">Chargement des groupes et des permissions…</Typography>;
  }
  if (groups.isError || permissions.isError) {
    const error = groups.error || permissions.error;
    return (
      <Alert severity="error">
        {denied(error) ? 'Accès non autorisé aux groupes ou aux permissions.' : apiErrorMessage(error)}
        <Button onClick={() => { groups.refetch(); permissions.refetch(); }}>Réessayer</Button>
      </Alert>
    );
  }

  const choose = (item, duplicate = false) => {
    setSelectedId(duplicate ? 'new' : item?.id ?? 'new');
    setName(duplicate ? `${item.name} (copie)` : item?.name ?? '');
    setPermissionIds(ids(item?.permissions) ?? []);
    setUserId('');
    setSelectionError('');
    setNotice('');
    save.reset();
    assign.reset();
  };
  const permissionsAvailable = selectedId === 'new' || Array.isArray(group?.permissions);
  const editable = (selectedId === 'new' ? canAdd : canChange) && permissionsAvailable;
  const busy = save.isPending || assign.isPending;
  const permissionsByApp = permissions.data.reduce((result, permission) => ({
    ...result, [permission.app_label]: [...(result[permission.app_label] || []), permission],
  }), {});

  return (
    <Paper component="section" variant="outlined" aria-label="Groupes d’autorisations" sx={{ p: { xs: 2, sm: 3 } }}>
      <Typography component="h2" variant="h6" gutterBottom>Groupes et permissions</Typography>
      <Typography sx={{ mb: 2 }}>
        Les groupes sont distincts du rôle métier des comptes. Les permissions proposées proviennent du serveur.
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        L’API ne permet pas de désactiver un groupe. La suppression, irréversible, n’est pas proposée ici.
      </Alert>
      {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}
      <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap', mb: 3 }}>
        {groups.data.map(item => (
          <Button
            key={item.id}
            variant={selectedId === item.id ? 'contained' : 'outlined'}
            onClick={() => choose(item)}
          >{item.name}
          </Button>
        ))}
        {groups.data.length === 0 && <Typography>Aucun groupe disponible.</Typography>}
        {canAdd && <Button onClick={() => choose(null)}>Créer un groupe</Button>}
      </Stack>
      {selectedId !== null && (
        <Box
          component="form"
          onSubmit={(event) => {
            event.preventDefault();
            setNotice('');
            if (!name.trim()) { setSelectionError('Le nom du groupe est requis.'); return; }
            setSelectionError('');
            save.mutate({ name: name.trim(), permissions: permissionIds });
          }}
        >
          <Typography component="h3" variant="subtitle1" gutterBottom>
            {selectedId === 'new' ? 'Nouveau groupe' : `Modifier ${group?.name || 'le groupe'}`}
          </Typography>
          {selectedId !== 'new' && group && canAdd && permissionsAvailable && (
            <Button type="button" disabled={busy} onClick={() => choose(group, true)} sx={{ mb: 2 }}>
              Dupliquer le groupe
            </Button>
          )}
          <TextField
            label="Nom du groupe"
            value={name}
            onChange={(event) => { setName(event.target.value); setSelectionError(''); }}
            disabled={!editable || busy}
            required
            fullWidth
            sx={{ mb: 2 }}
          />
          {Object.entries(permissionsByApp).map(([app, items]) => (
            <Box key={app} sx={{ mb: 2 }}>
              <Typography component="h4" variant="subtitle2">{app}</Typography>
              <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', gap: 1 }}>
                {items.map(permission => (
                  <FormControlLabel
                    key={permission.id}
                    label={`${permission.name} (${permission.codename})`}
                    control={(
                      <Checkbox
                        checked={permissionIds.some(id => String(id) === String(permission.id))}
                        disabled={!editable || busy}
                        onChange={(event) => {
                          setPermissionIds(current => (event.target.checked
                            ? [...current, permission.id]
                            : current.filter(id => String(id) !== String(permission.id))));
                        }}
                      />
                    )}
                  />
                ))}
              </Stack>
            </Box>
          ))}
          {selectionError && <Alert severity="error" sx={{ mb: 2 }}>{selectionError}</Alert>}
          {!permissionsAvailable && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Les permissions de ce groupe ne sont pas disponibles. Rechargez la liste avant de modifier ce groupe.
            </Alert>
          )}
          {save.isError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {denied(save.error) ? 'Enregistrement non autorisé.' : apiErrorMessage(save.error)}
            </Alert>
          )}
          {editable && <Button type="submit" variant="contained" disabled={busy || !name.trim()}>Enregistrer le groupe</Button>}
          {!editable && permissionsAvailable && (
            <Alert severity="warning">Modification non autorisée pour ce compte.</Alert>
          )}
          {selectedId !== 'new' && (
            <Box component="section" aria-label="Affectation des comptes" sx={{ mt: 3 }}>
              <Typography component="h3" variant="subtitle1" gutterBottom>Affecter des comptes</Typography>
              {!canAssign ? (
                <Alert severity="warning">
                  Affectation non autorisée : droits de modification des groupes et des comptes,
                  ainsi que de consultation des comptes requis.
                </Alert>
              ) : (
                <>
                  {users.isPending && <Typography role="status">Chargement des comptes…</Typography>}
                  {users.isError && (
                    <Alert severity="error">
                      {denied(users.error) ? 'Accès non autorisé aux comptes.' : apiErrorMessage(users.error)}
                      <Button onClick={() => users.refetch()}>Réessayer</Button>
                    </Alert>
                  )}
                  {users.isSuccess && (
                    <>
                      <TextField
                        select
                        label="Compte"
                        value={userId}
                        onChange={(event) => { setUserId(event.target.value); assign.reset(); }}
                        fullWidth
                        sx={{ my: 2 }}
                        disabled={busy}
                      >
                        <MenuItem value="">Sélectionner un compte</MenuItem>
                        {users.data.map(user => (
                          <MenuItem key={user.id} value={String(user.id)}>
                            {user.full_name || user.username} ({user.username})
                          </MenuItem>
                        ))}
                      </TextField>
                      {userId && !membership && (
                        <Alert severity="error">Les groupes de ce compte ne sont pas disponibles.</Alert>
                      )}
                      {selectedUser && membership && (
                        <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                          <Typography>{member ? 'Compte membre de ce groupe.' : 'Compte non membre de ce groupe.'}</Typography>
                          <Button
                            type="button"
                            variant="outlined"
                            disabled={busy}
                            onClick={() => { setNotice(''); assign.mutate(!member); }}
                          >{member ? 'Retirer du groupe' : 'Ajouter au groupe'}
                          </Button>
                        </Stack>
                      )}
                      {users.data.length === 0 && <Typography>Aucun compte disponible.</Typography>}
                    </>
                  )}
                  {assign.isError && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                      {denied(assign.error) ? 'Affectation non autorisée.' : apiErrorMessage(assign.error)}
                    </Alert>
                  )}
                </>
              )}
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

InstitutionalGroupsEditor.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  capabilities: PropTypes.shape({
    permissions: PropTypes.arrayOf(PropTypes.string),
    attributes: PropTypes.shape({
      permission_scopes: PropTypes.objectOf(PropTypes.objectOf(
        PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number])),
      )),
    }),
  }),
};
InstitutionalGroupsEditor.defaultProps = { capabilities: null };

export default InstitutionalGroupsEditor;
