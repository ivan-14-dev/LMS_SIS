import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Autocomplete, Button, Checkbox,
  Chip, FormControlLabel, Stack, TextField, Typography,
} from '@mui/material';
import { ExpandMore } from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, putApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';
import PermissionCatalog, { permissionCode } from './PermissionCatalog';

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
  const busy = save.isPending || !policy.editable;
  const effective = new Set(policy.effective_permissions || []);
  const sources = {};
  permissions.forEach(permission => {
    const code = permissionCode(permission);
    const origins = [];
    if (effective.has('*')) { origins.push('Super-utilisateur : tous les droits SIS'); }
    if (policy.user_permissions.includes(permission.id)) { origins.push('Ajout direct'); }
    (policy.permission_groups || []).filter(group => group.permissions.includes(code)).forEach(group => {
      origins.push(`Groupe ${group.name}${group.active ? '' : ' (désactivé)'}`);
    });
    if (policy.denied_permissions.includes(code)) { origins.push('Retrait individuel prioritaire'); }
    if (effective.has(code) && !origins.length) { origins.push('Accord serveur'); }
    if (origins.length) {
      if (policy.permission_scopes?.[code]) { origins.push(`Périmètre : ${JSON.stringify(policy.permission_scopes[code])}`); }
      sources[permission.id] = `${effective.has('*') || effective.has(code) ? 'Accordée' : 'Non accordée'} — ${origins.join(' ; ')}`;
    }
  });
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
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMore />}>Voir les droits enregistrés de ces rôles</AccordionSummary>
        <AccordionDetails>
          <Stack spacing={2}>
            <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
              {policy.roles.map(role => <Chip key={role.code} label={`${role.label}${role.code === policy.primary_role ? ' (principal)' : ''}`} />)}
            </Stack>
            <Alert severity="info">
              Un rôle métier n’est pas un groupe fixe de permissions. Cette vue montre les droits
              globaux enregistrés du compte, communs à ses rôles. Les affectations, liens parent-enfant,
              règles métier, permissions sur des objets et périmètres peuvent encore limiter ou ouvrir
              un accès contextuel. Les modifications du formulaire apparaîtront après enregistrement.
            </Alert>
            {policy.is_active === false && <Alert severity="warning">Compte désactivé : aucun droit utilisable.</Alert>}
            {policy.permission_groups && Array.isArray(policy.effective_permissions) ? (
              <>
                <Typography>
                  Groupes : {policy.permission_groups.length
                  ? policy.permission_groups.map(group => `${group.name}${group.active ? '' : ' (désactivé)'}`).join(', ')
                  : 'aucun'}
                </Typography>
                <PermissionCatalog
                  label="Droits enregistrés du compte"
                  permissions={permissions.filter(permission => sources[permission.id])}
                  value={permissions.filter(permission => effective.has('*') || effective.has(permissionCode(permission))).map(permission => permission.id)}
                  readOnly
                  details={sources}
                />
              </>
            ) : <Alert severity="warning">Le serveur ne fournit pas le détail des origines des permissions. Rechargez après sa mise à jour.</Alert>}
          </Stack>
        </AccordionDetails>
      </Accordion>
      <Autocomplete
        multiple
        disableCloseOnSelect
        options={policy.role_options}
        value={policy.role_options.filter(role => roles.includes(role.code))}
        getOptionLabel={role => role.label}
        isOptionEqualToValue={(left, right) => left.code === right.code}
        onChange={(_event, value) => setRoles(value.map(role => role.code))}
        disabled={busy || !policy.can_edit_roles}
        renderOption={(props, role, { selected }) => (
          <li {...props}><Checkbox checked={selected} tabIndex={-1} disableRipple />{role.label}</li>
        )}
        renderInput={params => <TextField {...params} label="Rôles supplémentaires" helperText="L’attribution des rôles métier est réservée aux super-utilisateurs." />}
      />
      <PermissionCatalog
        label="Permissions ajoutées directement"
        permissions={permissions}
        value={grants}
        onChange={setGrants}
        disabled={busy}
      />
      <PermissionCatalog
        label="Permissions explicitement retirées"
        permissions={permissions}
        value={permissions
          .filter(permission => denials.includes(permissionCode(permission))).map(permission => permission.id)}
        onChange={ids => setDenials([
          ...denials.filter(code => !permissions.some(permission => permissionCode(permission) === code)),
          ...permissions.filter(permission => ids.includes(permission.id)).map(permissionCode),
        ])}
        disabled={busy}
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
  is_active: PropTypes.bool,
  effective_permissions: PropTypes.arrayOf(PropTypes.string),
  permission_groups: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number,
    name: PropTypes.string,
    active: PropTypes.bool,
    permissions: PropTypes.arrayOf(PropTypes.string),
  })),
  permission_scopes: PropTypes.objectOf(PropTypes.objectOf(
    PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number])),
  )),
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
  const [roleFilter, setRoleFilter] = useState(null);
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
  const rolesOf = user => user.roles || [{ code: user.role, label: user.role_display || user.role }];
  const roleOptions = [...new Map(users.data.flatMap(rolesOf).filter(role => role.code)
    .map(role => [role.code, role])).values()];
  return (
    <Stack spacing={3}>
      <Autocomplete
        options={roleOptions}
        value={roleFilter}
        getOptionLabel={role => role.label}
        isOptionEqualToValue={(left, right) => left.code === right.code}
        onChange={(_event, role) => { setRoleFilter(role); setSelected(null); setNotice(''); }}
        renderInput={params => <TextField {...params} label="Filtrer les comptes par rôle" helperText="Rôle principal ou supplémentaire. Choisissez ensuite un compte pour voir ses droits réels." />}
      />
      <Autocomplete
        options={users.data.filter(user => !roleFilter || rolesOf(user).some(role => role.code === roleFilter.code))}
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
