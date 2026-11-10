import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Autocomplete, Button, Checkbox, FormControlLabel, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, putApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';

const PolicyForm = ({
  url, policy, permissions, onSaved,
}) => {
  const client = useQueryClient();
  const [roles, setRoles] = useState(policy.additional_roles);
  const [grants, setGrants] = useState(policy.user_permissions);
  const [denials, setDenials] = useState(policy.denied_permissions);
  const [disabled, setDisabled] = useState(policy.disabled_features);
  const save = useMutation({
    mutationFn: () => putApi(url, {
      version: policy.version,
      additional_roles: roles,
      user_permissions: grants,
      denied_permissions: denials,
      disabled_features: disabled,
    }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['account-access-policy', url] });
      await client.invalidateQueries({ queryKey: ['capabilities'] });
      onSaved();
    },
  });
  const code = permission => `${permission.app_label}.${permission.codename}`;
  const busy = save.isPending || !policy.editable;
  return (
    <Stack component="form" spacing={2} onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <Typography>
        Rôle principal : {policy.roles.find(role => role.code === policy.primary_role)?.label || policy.primary_role}
      </Typography>
      <Alert severity="info">
        Les retraits individuels priment sur les permissions directes, les groupes et les rôles.
        Les rôles ne créent pas de dossier métier ni d’affectation pédagogique.
        Le changement d’espace actif ne change pas le rôle principal du compte.
        Retirer la consultation des dossiers ou résultats bloque aussi le portail apprenant/famille
        qui les rassemble, afin de ne pas révéler ces informations par un autre écran.
      </Alert>
      {!policy.editable && <Alert severity="warning">Votre propre compte et les super-utilisateurs sont protégés.</Alert>}
      <Autocomplete
        multiple
        options={policy.role_options}
        value={policy.role_options.filter(role => roles.includes(role.code))}
        getOptionLabel={role => role.label}
        isOptionEqualToValue={(left, right) => left.code === right.code}
        onChange={(_event, value) => setRoles(value.map(role => role.code))}
        disabled={busy || !policy.can_edit_roles}
        renderInput={params => <TextField {...params} label="Rôles supplémentaires" helperText="L’attribution des rôles métier est réservée aux super-utilisateurs." />}
      />
      <Autocomplete
        multiple
        options={permissions}
        value={permissions.filter(permission => grants.includes(permission.id))}
        getOptionLabel={permission => `${permission.name} (${code(permission)})`}
        isOptionEqualToValue={(left, right) => left.id === right.id}
        onChange={(_event, value) => setGrants(value.map(permission => permission.id))}
        disabled={busy}
        renderInput={params => <TextField {...params} label="Permissions ajoutées directement" />}
      />
      <Autocomplete
        multiple
        options={permissions}
        value={permissions.filter(permission => denials.includes(code(permission)))}
        getOptionLabel={permission => `${permission.name} (${code(permission)})`}
        isOptionEqualToValue={(left, right) => left.id === right.id}
        onChange={(_event, value) => setDenials(value.map(code))}
        disabled={busy}
        renderInput={params => <TextField {...params} label="Permissions explicitement retirées" helperText="Un retrait reste prioritaire même si la permission est aussi ajoutée directement." />}
      />
      <Typography component="h3" variant="subtitle1">Retirer un accès personnel ou un service</Typography>
      {policy.features.map(feature => (
        <FormControlLabel
          key={feature.code}
          label={`Retirer : ${feature.label}`}
          control={(
            <Checkbox
              checked={disabled.includes(feature.code)}
              disabled={busy || (!policy.can_restore_features && policy.disabled_features.includes(feature.code))}
              onChange={event => setDisabled(current => (event.target.checked
                ? [...current, feature.code] : current.filter(value => value !== feature.code)))}
            />
          )}
        />
      ))}
      <Typography variant="body2">
        Les retraits LMS/Studio sont transmis par la synchronisation.
        Une réactivation nécessite de confirmer à nouveau les affectations LMS retirées.
        Les droits accordés directement dans Open edX ne sont pas gérés par ce formulaire.
      </Typography>
      {save.isError && <Alert severity="error">{apiErrorMessage(save.error)}</Alert>}
      <Button type="submit" variant="contained" disabled={busy}>Enregistrer les accès individuels</Button>
    </Stack>
  );
};

const policyShape = PropTypes.shape({
  version: PropTypes.string.isRequired,
  primary_role: PropTypes.string.isRequired,
  roles: PropTypes.arrayOf(PropTypes.shape({ code: PropTypes.string, label: PropTypes.string })).isRequired,
  role_options: PropTypes.arrayOf(PropTypes.shape({ code: PropTypes.string, label: PropTypes.string })).isRequired,
  additional_roles: PropTypes.arrayOf(PropTypes.string).isRequired,
  user_permissions: PropTypes.arrayOf(PropTypes.number).isRequired,
  denied_permissions: PropTypes.arrayOf(PropTypes.string).isRequired,
  disabled_features: PropTypes.arrayOf(PropTypes.string).isRequired,
  features: PropTypes.arrayOf(PropTypes.shape({ code: PropTypes.string, label: PropTypes.string })).isRequired,
  editable: PropTypes.bool.isRequired,
  can_edit_roles: PropTypes.bool.isRequired,
  can_restore_features: PropTypes.bool.isRequired,
});
PolicyForm.propTypes = {
  url: PropTypes.string.isRequired,
  policy: policyShape.isRequired,
  permissions: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number, app_label: PropTypes.string, codename: PropTypes.string, name: PropTypes.string,
  })).isRequired,
  onSaved: PropTypes.func.isRequired,
};

const AccountAccessEditor = ({ variant }) => {
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState('');
  const usersUrl = resourceUrl(variant, 'utilisateurs/comptes');
  const url = selected ? `${usersUrl}${selected.id}/access-policy/` : null;
  const users = useQuery({
    queryKey: ['account-access-users', usersUrl],
    queryFn: () => fetchAllResourcePages(usersUrl),
  });
  const permissions = useQuery({
    queryKey: ['account-access-permissions', variant],
    queryFn: () => fetchAllResourcePages(resourceUrl(variant, 'utilisateurs/permissions')),
  });
  const policy = useQuery({
    queryKey: ['account-access-policy', url],
    queryFn: () => fetchApi(url),
    enabled: Boolean(url),
    staleTime: 0,
  });
  if (users.isPending || permissions.isPending) { return <Typography role="status">Chargement des comptes et droits…</Typography>; }
  if (users.isError || permissions.isError) {
    return <Alert severity="error">{apiErrorMessage(users.error || permissions.error)}</Alert>;
  }
  return (
    <Stack spacing={3}>
      <Autocomplete
        options={users.data}
        value={selected}
        getOptionLabel={user => `${user.full_name || user.username} (${user.username})`}
        isOptionEqualToValue={(left, right) => left.id === right.id}
        onChange={(_event, user) => { setSelected(user); setNotice(''); }}
        renderInput={params => <TextField {...params} label="Compte à configurer" />}
      />
      {notice && <Alert severity="success">{notice}</Alert>}
      {selected && policy.isPending && <Typography role="status">Chargement des accès…</Typography>}
      {selected && policy.isError && <Alert severity="error">{apiErrorMessage(policy.error)}</Alert>}
      {selected && !policy.isPending && (
        <Button onClick={() => policy.refetch()}>Recharger les droits du compte</Button>
      )}
      {selected && policy.data && !policy.isError && (
        <PolicyForm
          key={`${url}:${policy.data.version}`}
          url={url}
          policy={policy.data}
          permissions={permissions.data}
          onSaved={() => setNotice('Accès individuels enregistrés.')}
        />
      )}
    </Stack>
  );
};
AccountAccessEditor.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default AccountAccessEditor;
